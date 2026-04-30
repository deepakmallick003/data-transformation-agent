"""Tool registry for AgentCore scaffold.

Each tool module registers a builder function under a short name.
At runtime the AGENT_TOOLS environment variable controls which tools are
loaded:

    AGENT_TOOLS=athena                     # Athena SQL only
    AGENT_TOOLS=knowledge_base             # Bedrock KB only
    AGENT_TOOLS=s3                         # S3 read-only only
    AGENT_TOOLS=athena,knowledge_base,s3    # all three
    AGENT_TOOLS=                           # no external tools (file-system only)

A builder function signature:

    def build(request_id: str) -> ToolBundle

where ToolBundle carries the MCP server name, the list of @tool-decorated
async functions, and the allowed_tool_names strings needed by ClaudeAgentOptions.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from claude_agent_sdk import create_sdk_mcp_server

logger = logging.getLogger(__name__)

# ---- Registry ---------------------------------------------------------------

_REGISTRY: dict[str, Callable[[str], "ToolBundle"]] = {}


def register(name: str) -> Callable:
    """Decorator that registers a tool-builder function under *name*."""

    def decorator(fn: Callable) -> Callable:
        _REGISTRY[name] = fn
        return fn

    return decorator


def available_tools() -> list[str]:
    return sorted(_REGISTRY)


# ---- Result type ------------------------------------------------------------

@dataclass
class ToolBundle:
    server_name: str
    tools: list[Any]                     # @tool decorated async functions
    allowed_tool_names: list[str]         # e.g. ["mcp__athena__execute_athena_query"]


# ---- Loader called by agent_app.py -----------------------------------------

def build_enabled_tools(request_id: str) -> tuple[dict[str, Any], list[str]]:
    """Read AGENT_TOOLS env var and build all selected tool bundles.

    Returns:
        mcp_servers   dict passed to ClaudeAgentOptions(mcp_servers=...)
        allowed_tools list passed to ClaudeAgentOptions(allowed_tools=...)
    """

    raw = os.getenv("AGENT_TOOLS", "")
    enabled = [t.strip() for t in raw.split(",") if t.strip()]

    mcp_servers: dict[str, Any] = {}
    allowed_tools: list[str] = ["Skill", "Read", "Write", "Bash"]

    if not enabled:
        logger.info("AGENT_TOOLS is empty - running with file-system tools only")
        return mcp_servers, allowed_tools

    unknown = [n for n in enabled if n not in _REGISTRY]

    if unknown:
        raise ValueError(
            f"Unknown tool(s) in AGENT_TOOLS: {unknown}. "
            f"Available: {available_tools()}"
        )

    for name in enabled:
        bundle = _REGISTRY[name](request_id)

        mcp_servers[bundle.server_name] = create_sdk_mcp_server(
            name=bundle.server_name,
            version="1.0.0",
            tools=bundle.tools,
        )

        allowed_tools.extend(bundle.allowed_tool_names)

        logger.info("Loaded tool: %s (server=%s)", name, bundle.server_name)

    return mcp_servers, allowed_tools