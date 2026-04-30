"""Athena read-only SQL tool.

Required environment variables:
    ATHENA_DATABASE         Database name (e.g. my_analytics)
    ATHENA_OUTPUT_LOCATION  S3 URI for query results (e.g. s3://bucket/prefix/)
    AWS_REGION              AWS region (default: us-east-1)
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import boto3
from claude_agent_sdk import tool

from tools.registry import ToolBundle, register

logger = logging.getLogger(__name__)

ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "")
ATHENA_OUTPUT = os.getenv("ATHENA_OUTPUT_LOCATION", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


@register("athena")
def build(request_id: str) -> ToolBundle:
    if not ATHENA_DATABASE or not ATHENA_OUTPUT:
        raise EnvironmentError(
            "ATHENA_DATABASE and ATHENA_OUTPUT_LOCATION environment variables "
            "are required for the 'athena' tool"
        )

    executor = AthenaQueryExecutor(
        database=ATHENA_DATABASE,
        output_location=ATHENA_OUTPUT,
        results_dir=f"/tmp/agentcore-athena/{request_id}",
        region=AWS_REGION,
    )

    @tool(
        "execute_athena_query",
        "Execute a read-only SQL query against Amazon Athena and download results as CSV into temporary local scratch",
        {"query": str, "local_filename": str},
    )
    async def execute_athena_query(args: dict) -> dict:
        query_text = args.get("query", "")
        local_filename = args.get("local_filename", "query_results.csv")

        try:
            result = executor.execute_and_download(
                query=query_text,
                local_filename=local_filename,
            )

            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result),
                    }
                ]
            }

        except Exception as exc:
            logger.exception("Athena query failed")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing query: {exc}",
                    }
                ],
                "isError": True,
            }

    return ToolBundle(
        server_name="athena",
        tools=[execute_athena_query],
        allowed_tool_names=["mcp__athena__execute_athena_query"],
    )


# ---- Executor class used by the builder above -------------------------------

class AthenaQueryExecutor:
    """Small, reusable Athena executor restricted to read-only SQL."""

    def __init__(
        self,
        database: str,
        output_location: str,
        results_dir: str,
        region: str,
    ) -> None:
        self.database = database
        self.output_location = output_location
        self.region = region
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.athena_client = boto3.client("athena", region_name=region)
        self.s3_client = boto3.client("s3", region_name=region)

    def _validate_query(self, query: str) -> None:
        query_str = query.strip().lower()

        if not (query_str.startswith("select") or query_str.startswith("with")):
            raise ValueError("Only SELECT/WITH queries are allowed")

    def execute_and_download(self, query: str, local_filename: str) -> dict:
        self._validate_query(query)

        start_resp = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": self.database},
            ResultConfiguration={"OutputLocation": self.output_location},
        )

        execution_id = start_resp["QueryExecutionId"]

        start_time = time.time()

        while True:
            resp = self.athena_client.get_query_execution(
                QueryExecutionId=execution_id
            )

            status = resp["QueryExecution"]["Status"]["State"]

            if status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                break

            time.sleep(1)

        if status != "SUCCEEDED":
            reason = resp["QueryExecution"]["Status"].get(
                "StateChangeReason",
                "Unknown",
            )
            raise RuntimeError(f"Athena query failed: {reason}")

        output_uri = resp["QueryExecution"]["ResultConfiguration"]["OutputLocation"]
        bucket_key = output_uri.replace("s3://", "", 1)
        bucket, key = bucket_key.split("/", 1)

        local_path = self.results_dir / local_filename

        self.s3_client.download_file(bucket, key, str(local_path))

        stats = resp["QueryExecution"].get("Statistics", {})

        return {
            "query_execution_id": execution_id,
            "local_file": str(local_path),
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "data_scanned_bytes": stats.get("DataScannedInBytes", 0),
        }
