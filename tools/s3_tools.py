"""S3 read-only tools (list and read objects).

Required environment variables:
    S3_BUCKET              Bucket name to grant access to
    AWS_REGION             AWS region (default: us-east-1)

Optional:
    S3_KEY_PREFIX          Restrict access to keys under this prefix (default: "")
    S3_MAX_LIST_RESULTS    Max keys returned by list operation (default: 100)
    S3_MAX_OBJECT_BYTES    Max bytes read per object (default: 1 MB)
"""

from __future__ import annotations

import logging
import os

import boto3
from botocore.config import Config
from claude_agent_sdk import tool

from tools.registry import ToolBundle, register

logger = logging.getLogger(__name__)

S3_BUCKET = os.getenv("S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_KEY_PREFIX = os.getenv("S3_KEY_PREFIX", "")
S3_MAX_LIST_RESULTS = int(os.getenv("S3_MAX_LIST_RESULTS", "100"))
S3_MAX_OBJECT_BYTES = int(
    os.getenv("S3_MAX_OBJECT_BYTES", str(1 * 1024 * 1024))
)  # 1 MB


@register("s3")
def build(request_id: str) -> ToolBundle:
    if not S3_BUCKET:
        raise EnvironmentError(
            "S3_BUCKET environment variable is required for the 's3' tool"
        )

    config = Config(signature_version="s3v4", region_name=AWS_REGION)
    s3_client = boto3.client("s3", config=config, region_name=AWS_REGION)

    def _safe_key(key: str) -> str:
        key = (key or "").strip().lstrip("/")

        if S3_KEY_PREFIX:
            prefix = S3_KEY_PREFIX.strip().strip("/")

            if key:
                if not key.startswith(prefix + "/") and key != prefix:
                    key = f"{prefix}/{key}"
            else:
                key = prefix

        return key

    @tool(
        "list_s3_objects",
        "List objects in the S3 bucket, optionally filtered by prefix",
        {"prefix": str},
    )
    async def list_s3_objects(args: dict) -> dict:
        prefix = _safe_key(args.get("prefix", ""))

        try:
            resp = s3_client.list_objects_v2(
                Bucket=S3_BUCKET,
                Prefix=prefix,
                MaxKeys=S3_MAX_LIST_RESULTS,
            )

            objects = resp.get("Contents", [])

            if not objects:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No objects found under s3://{S3_BUCKET}/{prefix}",
                        }
                    ]
                }

            lines = [
                f"Objects in s3://{S3_BUCKET}/{prefix} ({len(objects)} result(s)):\n"
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
        "Read the text content of an S3 object (read-only, max 1 MB)",
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
            resp = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
            size = resp["ContentLength"]

            if size > S3_MAX_OBJECT_BYTES:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Object s3://{S3_BUCKET}/{key} is {size / 1024:.1f} KB, "
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
                        "text": f"Content of s3://{S3_BUCKET}/{key}:\n\n{body}",
                    }
                ]
            }

        except s3_client.exceptions.NoSuchKey:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Object not found: s3://{S3_BUCKET}/{key}",
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

    return ToolBundle(
        server_name="s3",
        tools=[list_s3_objects, read_s3_object],
        allowed_tool_names=[
            "mcp__s3__list_s3_objects",
            "mcp__s3__read_s3_object",
        ],
    )