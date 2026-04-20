from __future__ import annotations

from typing import Any

from claude_agent_sdk import McpSdkServerConfig, create_sdk_mcp_server, tool

from app.runtime.mcp.annotations import MUTATING, READ_ONLY
from app.session.manager import SessionManager


def build_session_artifact_server(
    session_manager: SessionManager,
    session_id: str,
) -> McpSdkServerConfig:
    @tool(
        "list_session_assets",
        "List uploaded files, working artifacts, and generated outputs for the active session.",
        {},
        annotations=READ_ONLY,
    )
    async def list_session_assets(_: dict[str, Any]) -> dict[str, Any]:
        assets = session_manager.list_artifacts(session_id)
        lines = [
            f"- {item.kind}: {item.path} ({item.size_bytes} bytes)"
            for item in assets
        ] or ["- no session files yet"]
        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    @tool(
        "read_session_artifact",
        "Read one of the active session markdown artifacts by filename.",
        {"artifact_name": str},
        annotations=READ_ONLY,
    )
    async def read_session_artifact(args: dict[str, Any]) -> dict[str, Any]:
        content = session_manager.read_artifact(session_id, args["artifact_name"])
        return {"content": [{"type": "text", "text": content}]}

    @tool(
        "write_session_artifact",
        "Overwrite a session markdown artifact with updated structured content.",
        {"artifact_name": str, "content": str, "reason": str},
        annotations=MUTATING,
    )
    async def write_session_artifact(args: dict[str, Any]) -> dict[str, Any]:
        path = session_manager.write_artifact(
            session_id=session_id,
            artifact_name=args["artifact_name"],
            content=args["content"],
        )
        session_manager.record_activity(
            event="artifact-updated",
            title=f"Updated artifact {path.name}",
            detail=args["reason"],
            level="success",
            metadata={"artifact_name": path.name},
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Updated {path.name} for reason: {args['reason']}",
                }
            ]
        }

    @tool(
        "write_session_output",
        "Write a generated session deliverable into the outputs folder.",
        {"filename": str, "content": str, "description": str},
        annotations=MUTATING,
    )
    async def write_session_output(args: dict[str, Any]) -> dict[str, Any]:
        path = session_manager.write_output(
            session_id=session_id,
            filename=args["filename"],
            content=args["content"],
        )
        session_manager.record_activity(
            event="output-written",
            title=f"Wrote output {path.name}",
            detail=args["description"],
            level="success",
            metadata={"filename": path.name},
        )
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Wrote output file {path.relative_to(session_manager.session_root(session_id))} ({args['description']}).",
                }
            ]
        }

    return create_sdk_mcp_server(
        name="session_artifacts",
        version="1.0.0",
        tools=[
            list_session_assets,
            read_session_artifact,
            write_session_artifact,
            write_session_output,
        ],
    )
