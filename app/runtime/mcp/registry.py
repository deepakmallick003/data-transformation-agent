from __future__ import annotations

import sys
from dataclasses import dataclass

from claude_agent_sdk import McpServerConfig
from claude_agent_sdk.types import McpHttpServerConfig, McpSSEServerConfig, McpStdioServerConfig

from app.core.config import Settings
from app.runtime.mcp.servers.session_artifacts import build_session_artifact_server
from app.runtime.mcp.servers.session_context import build_session_context_server
from app.session.manager import SessionManager


@dataclass(frozen=True)
class RuntimeMcpConfig:
    servers: dict[str, McpServerConfig]
    allowed_tools: list[str]
    server_names: list[str]


def build_runtime_mcp_config(
    *,
    settings: Settings,
    session_manager: SessionManager,
    session_id: str,
) -> RuntimeMcpConfig:
    servers: dict[str, McpServerConfig] = {
        "session_artifacts": build_session_artifact_server(
            session_manager=session_manager,
            session_id=session_id,
        ),
        "session_context": build_session_context_server(
            session_manager=session_manager,
            session_id=session_id,
        ),
    }
    allowed_tools = [
        "mcp__session_artifacts__*",
        "mcp__session_context__*",
    ]

    if settings.local_insights_mcp_enabled:
        local_insights_server: McpStdioServerConfig = {
            "command": sys.executable,
            "args": [str(settings.local_insights_server_path)],
            "env": {"DATA_TRANSFORM_AGENT_PROJECT_ROOT": str(settings.project_root)},
        }
        servers["local_insights"] = local_insights_server
        allowed_tools.append("mcp__local_insights__*")

    if settings.github_mcp_enabled and settings.github_token:
        github_server: McpStdioServerConfig = {
            "command": settings.github_mcp_command,
            "args": settings.github_mcp_args_list,
            "env": {"GITHUB_TOKEN": settings.github_token},
        }
        servers["github"] = github_server
        allowed_tools.append("mcp__github__*")

    if settings.remote_mcp_enabled and settings.remote_mcp_url:
        if settings.remote_mcp_type == "http":
            remote_server: McpHttpServerConfig | McpSSEServerConfig = {
                "type": "http",
                "url": settings.remote_mcp_url,
            }
        else:
            remote_server = {
                "type": "sse",
                "url": settings.remote_mcp_url,
            }
        if settings.remote_mcp_bearer_token:
            remote_server["headers"] = {
                settings.remote_mcp_auth_header: f"Bearer {settings.remote_mcp_bearer_token}"
            }
        servers[settings.remote_mcp_name] = remote_server
        allowed_tools.append(f"mcp__{settings.remote_mcp_name}__*")

    return RuntimeMcpConfig(
        servers=servers,
        allowed_tools=allowed_tools,
        server_names=list(servers),
    )
