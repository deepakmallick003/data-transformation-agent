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
from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
)

# Ensure project root is on the path so tool imports resolve correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import tool modules so they self-register via @register(...)
import tools.athena_tools  # noqa: F401
import tools.knowledge_base_tools  # noqa: F401
import tools.s3_tools  # noqa: F401

from config.settings import resolve_agent_name
from tools.registry import build_enabled_tools
from tools.s3_tools import resolve_request_storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
PROMPT_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "config" / "templates" / "prompts" / "agent_prompt.md"
)


def render_system_prompt(
    *,
    agent_label: str,
    request_id: str,
    resolved_read_root: str,
    resolved_write_root: str,
    project_context: str,
) -> str:
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.format(
        agent_label=agent_label,
        request_id=request_id,
        resolved_read_root=resolved_read_root,
        resolved_write_root=resolved_write_root,
        project_context=project_context,
    )


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
    agent_name = resolve_agent_name()
    agent_label = agent_name.replace("-", " ").replace("_", " ").title()
    request_storage = resolve_request_storage(agent_name, request_id)

    claude_md_path = project_root / "CLAUDE.md"
    project_context = (
        claude_md_path.read_text(encoding="utf-8") if claude_md_path.exists() else ""
    )

    # Build only the tools declared in AGENT_TOOLS
    mcp_servers, allowed_tools = build_enabled_tools(request_id)

    system_prompt = render_system_prompt(
        agent_label=agent_label,
        request_id=request_id,
        resolved_read_root=request_storage.read_location.uri,
        resolved_write_root=request_storage.result_root_uri or "not configured",
        project_context=project_context,
    )

    options_kwargs: dict[str, Any] = {
        "system_prompt": system_prompt,
        "allowed_tools": allowed_tools,
        "mcp_servers": mcp_servers,
        "setting_sources": ["project"],
        "cwd": str(project_root),
        "max_turns": 30,
    }
    options = ClaudeAgentOptions(**options_kwargs)

    logger.info(
        "Starting request_id=%s agent_name=%s write_root=%s local_fallback=%s tools=%s",
        request_id,
        agent_name,
        request_storage.result_root_uri or "local-results-only",
        request_storage.local_result_root.as_posix(),
        allowed_tools,
    )
    async with ClaudeSDKClient(options=options) as client:
        await client.query(user_query)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                blocks = message.content
                for block in blocks:
                    if isinstance(block, TextBlock):
                        yield block.text


if __name__ == "__main__":
    app.run()
