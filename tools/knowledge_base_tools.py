"""Bedrock Knowledge Base retrieval tool.

Required environment variables:
    KNOWLEDGE_BASE_ID      Bedrock Knowledge Base ID (e.g. ABC123)
    AWS_REGION             AWS region (default: us-east-1)

Optional:
    KB_MAX_RESULTS         Max passages per query (default: 5)
"""

from __future__ import annotations

import logging
import os

import boto3
from claude_agent_sdk import tool

from tools.registry import ToolBundle, register

logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
KB_MAX_RESULTS = int(os.getenv("KB_MAX_RESULTS", "5"))


@register("knowledge_base")
def build(request_id: str) -> ToolBundle:
    if not KNOWLEDGE_BASE_ID:
        raise EnvironmentError(
            "KNOWLEDGE_BASE_ID environment variable is required for the 'knowledge_base' tool"
        )

    bedrock_agent_runtime = boto3.client(
        "bedrock-agent-runtime",
        region_name=AWS_REGION,
    )

    @tool(
        "retrieve_from_knowledge_base",
        "Retrieve relevant passages from the Bedrock Knowledge Base using semantic search",
        {"query": str},
    )
    async def retrieve_from_knowledge_base(args: dict) -> dict:
        query = args.get("query", "").strip()

        if not query:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: query must not be empty",
                    }
                ],
                "isError": True,
            }

        try:
            response = bedrock_agent_runtime.retrieve(
                knowledgeBaseId=KNOWLEDGE_BASE_ID,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {
                        "numberOfResults": KB_MAX_RESULTS,
                    }
                },
            )

            passages = response.get("retrievalResults", [])

            if not passages:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "No results found for the query.",
                        }
                    ]
                }

            lines: list[str] = [
                f"Retrieved {len(passages)} passage(s):\n"
            ]

            for i, passage in enumerate(passages, 1):
                content = passage.get("content", {}).get("text", "")
                location = passage.get("location", {})
                source = (
                    location.get("s3Location", {}).get("uri", "")
                    or str(location)
                )
                score = round(passage.get("score", 0), 4)

                lines.append(
                    f"[{i}] Score: {score}  Source: {source}\n{content}\n"
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
            logger.exception("Knowledge base retrieval failed")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error retrieving from knowledge base: {exc}",
                    }
                ],
                "isError": True,
            }

    return ToolBundle(
        server_name="knowledge_base",
        tools=[retrieve_from_knowledge_base],
        allowed_tool_names=[
            "mcp__knowledge_base__retrieve_from_knowledge_base",
        ],
    )