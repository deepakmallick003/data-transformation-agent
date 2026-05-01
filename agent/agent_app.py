#!/usr/bin/env python3
"""Production runtime for HMRC Data Transformation Agent.

Tools are opt-in via the AGENT_TOOLS environment variable:

    AGENT_TOOLS=athena
    AGENT_TOOLS=knowledge_base
    AGENT_TOOLS=s3
    AGENT_TOOLS=athena,knowledge_base,s3   # combine freely
    AGENT_TOOLS=                         # file-system tools only

See tools/registry.py and each tool module for required env vars per tool.
"""

import logging
import sys
import uuid
from pathlib import Path

from bedrock_agentcore import BedrockAgentCoreApp
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

# Ensure project root is on the path so tool imports resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import tool modules so they self-register via @register(...)
import tools.athena_tools  # noqa: F401
import tools.knowledge_base_tools  # noqa: F401
import tools.s3_tools  # noqa: F401

from tools.registry import build_enabled_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()


@app.entrypoint
async def main(payload: dict | None = None):
    """AgentCore entrypoint - tools are loaded dynamically from AGENT_TOOLS."""
    request_id = str(uuid.uuid4())

    if payload is None or "query" not in payload:
        yield {
            "error": "Missing 'query' field in payload",
            "example": {"query": "What can you help me with?"},
        }
        return

    user_query = payload["query"]
    project_root = Path(__file__).parent.parent
    request_dir = project_root / "results" / request_id / "request"
    deliverables_dir = project_root / "results" / request_id / "deliverables"

    claude_md_path = project_root / "CLAUDE.md"
    project_context = (
        claude_md_path.read_text(encoding="utf-8") if claude_md_path.exists() else ""
    )

    request_dir.mkdir(parents=True, exist_ok=True)
    deliverables_dir.mkdir(parents=True, exist_ok=True)

    # Build only the tools declared in AGENT_TOOLS
    mcp_servers, allowed_tools = build_enabled_tools(request_id)

    options = ClaudeAgentOptions(
        system_prompt=(
            "You are HMRC Data Transformation Agent.\n\n"
            f"IMPORTANT: This request has ID: {request_id}\n"
            f"- External tool output must be saved to results/{request_id}/request/\n"
            f"- Processed output must be saved to results/{request_id}/deliverables/\n\n"
            f"{project_context}\n"
        ),
        allowed_tools=allowed_tools,
        mcp_servers=mcp_servers,
        setting_sources=["project"],
        cwd=str(project_root),
        max_turns=30,
    )

    logger.info("Starting request_id=%s tools=%s", request_id, allowed_tools)
    async with ClaudeSDKClient(options=options) as client:
        await client.query(user_query)
        async for message in client.receive_response():
            if hasattr(message, "content"):
                blocks = (
                    message.content
                    if isinstance(message.content, list)
                    else [message.content]
                )
                for block in blocks:
                    if hasattr(block, "text"):
                        yield block.text


if __name__ == "__main__":
    app.run()
