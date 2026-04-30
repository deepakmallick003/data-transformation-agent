"""S3 tools for source reads plus request-scoped writes with local fallback.

Required environment variables:
    AWS_REGION             AWS region (default: us-east-1)

Optional:
    S3_READ_BUCKET         Bucket used for source reads
    S3_READ_PREFIX         Prefix used for source reads
    S3_WRITE_BUCKET        Bucket used for primary request-scoped writes
    S3_MAX_LIST_RESULTS    Max keys returned by list operation (default: 100)
    S3_MAX_OBJECT_BYTES    Max bytes read per object (default: 1 MB)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from claude_agent_sdk import tool

from config.settings import resolve_agent_name
from tools.registry import ToolBundle, register

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_MAX_LIST_RESULTS = int(os.getenv("S3_MAX_LIST_RESULTS", "100"))
S3_MAX_OBJECT_BYTES = int(
    os.getenv("S3_MAX_OBJECT_BYTES", str(1 * 1024 * 1024))
)  # 1 MB


def normalize_s3_prefix(prefix: str) -> str:
    """Normalize an S3 prefix to either '' or 'path/' form."""
    cleaned = prefix.strip().strip("/")
    return f"{cleaned}/" if cleaned else ""


@dataclass(frozen=True)
class S3Settings:
    read_bucket: str
    read_prefix: str
    write_bucket: str
    write_prefix: str

    @property
    def read_object_path(self) -> str:
        return f"{self.read_prefix}*" if self.read_prefix else "*"

    @property
    def write_object_path(self) -> str:
        return f"{self.write_prefix}*" if self.write_prefix else "*"


def resolve_s3_settings(
    agent_name: str | None = None,
    default_read_bucket: str = "",
) -> S3Settings:
    """Resolve the configured S3 read/write settings."""
    write_bucket = os.getenv("S3_WRITE_BUCKET", "").strip()
    if write_bucket:
        write_prefix = normalize_s3_prefix(f"agents/{agent_name or resolve_agent_name()}/")
    else:
        write_prefix = ""

    return S3Settings(
        read_bucket=os.getenv("S3_READ_BUCKET", "").strip() or default_read_bucket,
        read_prefix=normalize_s3_prefix(os.getenv("S3_READ_PREFIX", "").strip()),
        write_bucket=write_bucket,
        write_prefix=write_prefix,
    )


def _require_bucket(bucket: str, env_hint: str) -> str:
    if not bucket:
        raise EnvironmentError(f"{env_hint} environment variable is required for S3 storage")
    return bucket


def _request_file_key(result_root_prefix: str, folder: str, filename: str) -> str:
    safe_name = Path(filename or "").name
    if not safe_name:
        raise ValueError("filename must not be empty")
    return f"{result_root_prefix}{folder}/{safe_name}"


def _local_results_root(request_id: str) -> Path:
    return Path("results") / request_id


def _local_request_file(local_results_root: Path, folder: str, filename: str) -> Path:
    safe_name = Path(filename or "").name
    if not safe_name:
        raise ValueError("filename must not be empty")
    return local_results_root / folder / safe_name


@dataclass(frozen=True)
class S3Location:
    bucket: str
    prefix: str

    @property
    def uri(self) -> str:
        return f"s3://{self.bucket}/{self.prefix}" if self.prefix else f"s3://{self.bucket}"


@dataclass(frozen=True)
class RequestStorage:
    read_location: S3Location
    write_location: S3Location | None
    result_root_prefix: str | None
    result_root_uri: str | None
    local_result_root: Path


def resolve_request_storage(agent_name: str, request_id: str) -> RequestStorage:
    s3_settings = resolve_s3_settings(agent_name)
    read_location = S3Location(
        bucket=_require_bucket(
            s3_settings.read_bucket,
            "S3_READ_BUCKET",
        ),
        prefix=s3_settings.read_prefix,
    )
    write_bucket = s3_settings.write_bucket
    write_location = None
    result_root_prefix = None
    result_root_uri = None
    if write_bucket:
        write_location = S3Location(
            bucket=write_bucket,
            prefix=s3_settings.write_prefix,
        )
        result_root_prefix = f"{write_location.prefix}results/{request_id}/"
        result_root_uri = f"s3://{write_location.bucket}/{result_root_prefix}"
    local_result_root = _local_results_root(request_id)
    return RequestStorage(
        read_location=read_location,
        write_location=write_location,
        result_root_prefix=result_root_prefix,
        result_root_uri=result_root_uri,
        local_result_root=local_result_root,
    )


@register("s3")
def build(request_id: str) -> ToolBundle:
    s3_settings = resolve_s3_settings(resolve_agent_name())
    read_bucket = s3_settings.read_bucket
    if not read_bucket:
        raise EnvironmentError(
            "S3_READ_BUCKET environment variable is required for the 's3' tool"
        )

    config = Config(signature_version="s3v4", region_name=AWS_REGION)
    s3_client = boto3.client("s3", config=config, region_name=AWS_REGION)
    request_storage = resolve_request_storage(resolve_agent_name(), request_id)

    def _safe_key(key: str) -> str:
        key = (key or "").strip().lstrip("/")
        read_prefix = s3_settings.read_prefix

        if read_prefix:
            prefix = read_prefix.strip("/")

            if key:
                if not key.startswith(prefix + "/") and key != prefix:
                    key = f"{prefix}/{key}"
            else:
                key = prefix

        return key

    @tool(
        "list_s3_objects",
        "List source objects in the configured S3 read bucket, optionally filtered by prefix",
        {"prefix": str},
    )
    async def list_s3_objects(args: dict) -> dict:
        prefix = _safe_key(args.get("prefix", ""))

        try:
            resp = s3_client.list_objects_v2(
                Bucket=read_bucket,
                Prefix=prefix,
                MaxKeys=S3_MAX_LIST_RESULTS,
            )

            objects = resp.get("Contents", [])

            if not objects:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No objects found under s3://{read_bucket}/{prefix}",
                        }
                    ]
                }

            lines = [
                f"Objects in s3://{read_bucket}/{prefix} ({len(objects)} result(s)):\n"
            ]

            for obj in objects:
                size_kb = obj["Size"] / 1024
                lines.append(
                    f"- {obj['Key']} ({size_kb:.1f} KB)  {obj['LastModified']}"
                )

            return {
                "content": [
                    {
                        "type": "text",
                        "text": "\n".join(lines),
                    }
                ]
            }

        except Exception as exc:
            logger.exception("S3 list failed")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error listing S3 objects: {exc}",
                    }
                ],
                "isError": True,
            }

    @tool(
        "read_s3_object",
        "Read the text content of an S3 source object (read-only, max 1 MB)",
        {"key": str},
    )
    async def read_s3_object(args: dict) -> dict:
        key = _safe_key(args.get("key", ""))

        if not key:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: key must not be empty",
                    }
                ],
                "isError": True,
            }

        try:
            resp = s3_client.get_object(Bucket=read_bucket, Key=key)
            size = resp["ContentLength"]

            if size > S3_MAX_OBJECT_BYTES:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Object s3://{read_bucket}/{key} is {size / 1024:.1f} KB, "
                                f"which exceeds the {S3_MAX_OBJECT_BYTES // 1024} KB read limit. "
                                "Use a more specific key or increase S3_MAX_OBJECT_BYTES."
                            ),
                        }
                    ],
                    "isError": True,
                }

            body = resp["Body"].read().decode("utf-8", errors="replace")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Content of s3://{read_bucket}/{key}:\n\n{body}",
                    }
                ]
            }

        except s3_client.exceptions.NoSuchKey:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Object not found: s3://{read_bucket}/{key}",
                    }
                ],
                "isError": True,
            }

        except Exception as exc:
            logger.exception("S3 read failed")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error reading S3 object: {exc}",
                    }
                ],
                "isError": True,
            }

    @tool(
        "write_request_s3_file",
        "Write a text file into the request-scoped request/ or deliverables/ folder, using S3 when configured and local results/ fallback otherwise",
        {"folder": str, "filename": str, "content": str},
    )
    async def write_request_s3_file(args: dict) -> dict:
        folder = (args.get("folder", "") or "").strip()
        filename = args.get("filename", "")
        content = args.get("content", "")

        if folder not in {"request", "deliverables"}:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: folder must be either 'request' or 'deliverables'",
                    }
                ],
                "isError": True,
            }

        try:
            local_path = _local_request_file(request_storage.local_result_root, folder, filename)
        except ValueError as exc:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {exc}",
                    }
                ],
                "isError": True,
            }

        if not request_storage.write_location or not request_storage.result_root_prefix:
            try:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_text(content, encoding="utf-8")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "S3 write is not configured for this runtime; "
                                f"stored locally at {local_path.as_posix()}"
                            ),
                        }
                    ]
                }
            except Exception as exc:
                logger.exception("Local request-scoped fallback write failed")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error writing local fallback file: {exc}",
                        }
                    ],
                    "isError": True,
                }

        try:
            key = _request_file_key(request_storage.result_root_prefix, folder, filename)
            s3_client.put_object(
                Bucket=request_storage.write_location.bucket,
                Key=key,
                Body=content.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )
            uri = f"s3://{request_storage.write_location.bucket}/{key}"
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Wrote file to {uri}",
                    }
                ]
            }
        except (ClientError, Exception) as exc:
            logger.warning("S3 request-scoped write failed; falling back to local results", exc_info=True)
            try:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_text(content, encoding="utf-8")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"S3 write unavailable ({exc}); "
                                f"stored locally at {local_path.as_posix()}"
                            ),
                        }
                    ]
                }
            except Exception as local_exc:
                logger.exception("Local fallback write failed after S3 failure")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Error writing S3 file ({exc}) and local fallback file "
                                f"({local_exc})"
                            ),
                        }
                    ],
                    "isError": True,
                }

    return ToolBundle(
        server_name="s3",
        tools=[list_s3_objects, read_s3_object, write_request_s3_file],
        allowed_tool_names=[
            "mcp__s3__list_s3_objects",
            "mcp__s3__read_s3_object",
            "mcp__s3__write_request_s3_file",
        ],
    )
