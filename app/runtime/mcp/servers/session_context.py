from __future__ import annotations

from typing import Any

from claude_agent_sdk import McpSdkServerConfig, create_sdk_mcp_server, tool

from app.runtime.mcp.annotations import READ_ONLY
from app.session.manager import SessionManager
from app.session.templates import list_template_definitions, read_template


def build_session_context_server(
    session_manager: SessionManager,
    session_id: str,
) -> McpSdkServerConfig:
    @tool(
        "describe_session_context",
        "Summarize the current session metadata, notes, uploads, artifacts, and outputs.",
        {},
        annotations=READ_ONLY,
    )
    async def describe_session_context(_: dict[str, Any]) -> dict[str, Any]:
        session = session_manager.get_session(session_id)
        uploads = session_manager.list_uploaded_files(session_id)
        assets = session_manager.list_artifacts(session_id)
        artifacts = [item.path for item in assets if item.kind == "artifact"]
        outputs = [item.path for item in assets if item.kind == "output"]

        lines = [
            f"Session ID: {session.id}",
            f"Title: {session.title}",
            "Notes:",
            session.notes or "No notes supplied yet.",
            "Uploads:",
            *(uploads or ["- none uploaded yet"]),
            "Artifacts:",
            *(artifacts or ["- no artifacts yet"]),
            "Outputs:",
            *(outputs or ["- no outputs yet"]),
        ]
        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    @tool(
        "read_session_upload",
        "Read a text upload from the active session by filename.",
        {"upload_name": str},
        annotations=READ_ONLY,
    )
    async def read_session_upload(args: dict[str, Any]) -> dict[str, Any]:
        content = session_manager.read_upload(session_id, args["upload_name"])
        return {"content": [{"type": "text", "text": content}]}

    @tool(
        "list_template_blueprints",
        "List the session artifact templates that seed new transformation sessions.",
        {},
        annotations=READ_ONLY,
    )
    async def list_template_blueprints(_: dict[str, Any]) -> dict[str, Any]:
        definitions = list_template_definitions()
        lines = [
            (
                f"- {definition.destination} (source template: {definition.source}; "
                f"title: {definition.title}; capabilities: {', '.join(definition.capabilities)})"
            )
            for definition in definitions
        ]
        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    @tool(
        "read_template_blueprint",
        "Read one of the markdown templates used to initialize a new session artifact.",
        {"template_name": str},
        annotations=READ_ONLY,
    )
    async def read_template_blueprint(args: dict[str, Any]) -> dict[str, Any]:
        content = read_template(session_manager.templates_root, args["template_name"])
        return {"content": [{"type": "text", "text": content}]}

    return create_sdk_mcp_server(
        name="session_context",
        version="1.0.0",
        tools=[
            describe_session_context,
            read_session_upload,
            list_template_blueprints,
            read_template_blueprint,
        ],
    )
