"""S3 tools for source reads plus optional request-scoped raw/processed writes.

Required environment variables:
    AWS_REGION             AWS region (default: us-east-1)

Optional:
    S3_READ_BUCKET         Bucket used for source reads
    S3_READ_PREFIX         Prefix used for source reads
    S3_WRITE_BUCKET        Bucket used for request-scoped S3 writes
    S3_WRITE_PREFIX        Base prefix for agent-scoped S3 writes (default: agents)
    DEFAULT_STORAGE_MODE   local, s3, or mirror (default: local)
    S3_MAX_LIST_RESULTS    Max keys returned by list operation (default: 100)
    S3_MAX_OBJECT_BYTES    Max bytes read per object (default: 1 MB)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from claude_agent_sdk import tool

from tools.registry import ToolBundle, register

logger = logging.getLogger(__name__)

DEFAULT_AGENT_NAME = "hmrc-data-transformation-agent"
FALLBACK_AGENT_NAME = "agentcore_agent"
VALID_STORAGE_MODES = {"local", "s3", "mirror"}


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _agent_name() -> str:
    raw_name = _env("AGENTCORE_AGENT_NAME", DEFAULT_AGENT_NAME)
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw_name)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    cleaned = cleaned.strip("_").lower()
    return cleaned[:47] or FALLBACK_AGENT_NAME


def _clean_prefix(prefix: str) -> str:
    return prefix.strip().strip("/")


def _prefixed_read_key(key: str, read_prefix: str) -> str:
    key = (key or "").strip().lstrip("/")
    if not read_prefix:
        return key
    if not key:
        return read_prefix
    if key == read_prefix or key.startswith(read_prefix + "/"):
        return key
    return f"{read_prefix}/{key}"


def _relative_path(relative_path: str) -> str:
    raw = (relative_path or "").strip().strip("/")
    if not raw:
        return ""
    parts = Path(raw).parts
    if any(part in {"..", "."} for part in parts):
        raise ValueError("relative_path must stay within the request-scoped result folder")
    return "/".join(parts)


def _storage_mode(requested_mode: str) -> str:
    mode = (requested_mode or _env("DEFAULT_STORAGE_MODE", "local")).strip().lower()
    if mode not in VALID_STORAGE_MODES:
        raise ValueError("storage_mode must be one of: local, s3, mirror")
    return mode


def _s3_result_root(request_id: str) -> str:
    base_prefix = _clean_prefix(_env("S3_WRITE_PREFIX", "agents"))
    parts = [part for part in [base_prefix, _agent_name(), "results"] if part]
    return "/".join(parts)


def _s3_result_key(request_id: str, folder: str, relative_path: str, filename: str) -> str:
    safe_name = Path(filename or "").name
    if not safe_name:
        raise ValueError("filename must not be empty")
    path_parts = [_s3_result_root(request_id), folder, request_id]
    nested = _relative_path(relative_path)
    if nested:
        path_parts.append(nested)
    path_parts.append(safe_name)
    return "/".join(path_parts)


def _local_result_file(request_id: str, folder: str, relative_path: str, filename: str) -> Path:
    safe_name = Path(filename or "").name
    if not safe_name:
        raise ValueError("filename must not be empty")
    path = Path("results") / folder / request_id
    nested = _relative_path(relative_path)
    if nested:
        path /= nested
    return path / safe_name


def _write_local_file(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path.as_posix()


@register("s3")
def build(request_id: str) -> ToolBundle:
    aws_region = _env("AWS_REGION", "us-east-1")
    read_bucket = _env("S3_READ_BUCKET")
    read_prefix = _clean_prefix(_env("S3_READ_PREFIX"))
    write_bucket = _env("S3_WRITE_BUCKET")
    s3_max_list_results = int(_env("S3_MAX_LIST_RESULTS", "100"))
    s3_max_object_bytes = int(_env("S3_MAX_OBJECT_BYTES", str(1 * 1024 * 1024)))

    if not read_bucket and not write_bucket:
        raise EnvironmentError(
            "At least one of S3_READ_BUCKET or S3_WRITE_BUCKET is required for the 's3' tool"
        )

    config = Config(signature_version="s3v4", region_name=aws_region)
    s3_client = boto3.client("s3", config=config, region_name=aws_region)

    @tool(
        "list_s3_objects",
        "List source objects in the configured S3 read bucket, optionally filtered by prefix",
        {"prefix": str},
    )
    async def list_s3_objects(args: dict) -> dict:
        if not read_bucket:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: S3_READ_BUCKET is not configured for this runtime",
                    }
                ],
                "isError": True,
            }

        prefix = _prefixed_read_key(args.get("prefix", ""), read_prefix)

        try:
            resp = s3_client.list_objects_v2(
                Bucket=read_bucket,
                Prefix=prefix,
                MaxKeys=s3_max_list_results,
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

            lines = [f"Objects in s3://{read_bucket}/{prefix} ({len(objects)} result(s)):\n"]
            for obj in objects:
                size_kb = obj["Size"] / 1024
                lines.append(f"- {obj['Key']} ({size_kb:.1f} KB)  {obj['LastModified']}")

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
        if not read_bucket:
            logger.error("S3 read failed because S3_READ_BUCKET is not configured")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: S3_READ_BUCKET is not configured for this runtime",
                    }
                ],
                "isError": True,
            }

        key = _prefixed_read_key(args.get("key", ""), read_prefix)
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

            if size > s3_max_object_bytes:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Object s3://{read_bucket}/{key} is {size / 1024:.1f} KB, "
                                f"which exceeds the {s3_max_object_bytes // 1024} KB read limit. "
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
            logger.exception(
                "S3 read failed bucket=%s key=%s request_id=%s",
                read_bucket,
                key,
                request_id,
            )
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
        "Store a request-scoped text file locally, in S3, or both. Use folder=raw or processed and choose storage_mode=local, s3, or mirror.",
        {
            "folder": str,
            "filename": str,
            "content": str,
            "storage_mode": str,
            "relative_path": str,
        },
    )
    async def write_request_s3_file(args: dict) -> dict:
        folder = (args.get("folder", "") or "").strip()
        filename = args.get("filename", "")
        content = args.get("content", "")
        relative_path = args.get("relative_path", "")

        if folder not in {"raw", "processed"}:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: folder must be either 'raw' or 'processed'",
                    }
                ],
                "isError": True,
            }

        try:
            mode = _storage_mode(args.get("storage_mode", ""))
            local_path = _local_result_file(request_id, folder, relative_path, filename)
            s3_key = _s3_result_key(request_id, folder, relative_path, filename)
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

        messages: list[str] = []

        if mode in {"local", "mirror"}:
            try:
                messages.append(f"Stored locally at {_write_local_file(local_path, content)}")
            except Exception as exc:
                logger.exception("Local request-scoped write failed")
                return {
                    "content": [
                        {
                            "type": "text",
                        "text": f"Error writing local result file: {exc}",
                        }
                    ],
                    "isError": True,
                }

        if mode in {"s3", "mirror"}:
            if not write_bucket:
                if mode == "mirror":
                    logger.warning(
                        "S3 mirror skipped because S3_WRITE_BUCKET is not configured "
                        "request_id=%s folder=%s filename=%s",
                        request_id,
                        folder,
                        filename,
                    )
                    messages.append("S3 mirror skipped because S3_WRITE_BUCKET is not configured")
                else:
                    logger.error(
                        "S3 write failed because S3_WRITE_BUCKET is not configured "
                        "request_id=%s folder=%s filename=%s",
                        request_id,
                        folder,
                        filename,
                    )
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": "Error: S3_WRITE_BUCKET is not configured for this runtime",
                            }
                        ],
                        "isError": True,
                    }
            else:
                try:
                    s3_client.put_object(
                        Bucket=write_bucket,
                        Key=s3_key,
                        Body=content.encode("utf-8"),
                        ContentType="text/plain; charset=utf-8",
                    )
                    messages.append(f"Stored in s3://{write_bucket}/{s3_key}")
                except (ClientError, Exception) as exc:
                    log_fn = logger.warning if mode == "mirror" else logger.exception
                    log_fn(
                        "S3 request-scoped write failed bucket=%s key=%s request_id=%s "
                        "folder=%s filename=%s mode=%s",
                        write_bucket,
                        s3_key,
                        request_id,
                        folder,
                        filename,
                        mode,
                        exc_info=True,
                    )
                    if mode == "mirror":
                        messages.append(f"S3 mirror failed ({exc})")
                    else:
                        return {
                            "content": [
                                {
                                    "type": "text",
                        "text": f"Error writing S3 result file: {exc}",
                                }
                            ],
                            "isError": True,
                        }

        return {
            "content": [
                {
                    "type": "text",
                    "text": "\n".join(messages),
                }
            ]
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
