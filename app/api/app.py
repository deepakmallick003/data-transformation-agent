from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.models import ChatRequest, ChatResponse, RuntimeActivityEntry, RuntimeState
from app.runtime.agent import AgentRunError, ClaudeTransformationAgent
from app.session.manager import SessionManager


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    session_manager = SessionManager(
        sessions_root=settings.sessions_root,
        templates_root=settings.templates_root,
    )
    agent = ClaudeTransformationAgent(settings=settings, session_manager=session_manager)

    app = FastAPI(
        title="Data Transformation Agent API",
        version="0.1.0",
        description="FastAPI backend for a Claude Agent SDK powered transformation assistant.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    abilities = [
        {
            "slash": "/agent",
            "label": "General Agent",
            "workflow": "general",
            "skills": [
                "transformation-discovery",
                "dependency-mapping",
                "delivery-planning",
                "transformation-delivery-helper:authority-check",
            ],
            "description": "Use the full transformation agent with all bundled skills enabled.",
        },
        {
            "slash": "/discover",
            "label": "Discovery",
            "workflow": "discovery",
            "skills": ["transformation-discovery"],
            "description": "Clarify the request, source systems, target systems, constraints, and unknowns.",
        },
        {
            "slash": "/map",
            "label": "Dependency Map",
            "workflow": "dependency-mapping",
            "skills": ["dependency-mapping"],
            "description": "Trace joins, sequencing, lineage, validation points, and system coupling.",
        },
        {
            "slash": "/plan",
            "label": "Delivery Plan",
            "workflow": "delivery-planning",
            "skills": [
                "delivery-planning",
                "transformation-delivery-helper:authority-check",
            ],
            "description": "Shape implementation steps, sign-offs, testing, and delivery packaging.",
        },
        {
            "slash": "/authority",
            "label": "Authority Check",
            "workflow": "delivery-planning",
            "skills": ["transformation-delivery-helper:authority-check"],
            "description": "Focus on approval needs, evidence gaps, and authority checkpoints.",
        },
    ]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runtime/capabilities")
    async def runtime_capabilities() -> dict[str, Any]:
        mcp_servers = [
            {
                "name": "session_artifacts",
                "transport": "sdk",
                "allowed_tool_glob": "mcp__session_artifacts__*",
                "purpose": "Read and write the runtime artifacts and generated outputs.",
            },
            {
                "name": "session_context",
                "transport": "sdk",
                "allowed_tool_glob": "mcp__session_context__*",
                "purpose": "Inspect runtime notes, uploads, and template blueprints.",
            },
        ]
        if settings.local_insights_mcp_enabled:
            mcp_servers.append(
                {
                    "name": "local_insights",
                    "transport": "stdio",
                    "allowed_tool_glob": "mcp__local_insights__*",
                    "purpose": "Runtime and repository diagnostics exposed through a separate MCP process.",
                }
            )
        if settings.github_mcp_enabled and settings.github_token:
            mcp_servers.append(
                {
                    "name": "github",
                    "transport": "stdio",
                    "allowed_tool_glob": "mcp__github__*",
                    "purpose": "Optional GitHub MCP integration configured from environment variables.",
                }
            )
        if settings.remote_mcp_enabled and settings.remote_mcp_url:
            mcp_servers.append(
                {
                    "name": settings.remote_mcp_name,
                    "transport": settings.remote_mcp_type,
                    "allowed_tool_glob": f"mcp__{settings.remote_mcp_name}__*",
                    "purpose": "Optional remote MCP integration configured from environment variables.",
                }
            )

        return {
            "session_mode": "ephemeral-runtime",
            "tool_search": {"ENABLE_TOOL_SEARCH": "auto:5"},
            "skills": list(dict.fromkeys(skill for ability in abilities for skill in ability["skills"])),
            "abilities": abilities,
            "subagents": [
                "requirements-analyst",
                "dependency-mapper",
                "implementation-planner",
            ],
            "mcp_servers": mcp_servers,
            "runtime": {
                "session_id": session_manager.active_session_id,
                "claude_cli_available": bool(settings.resolved_claude_cli_path),
                "claude_cli_path": settings.resolved_claude_cli_path or settings.claude_cli_path,
                "anthropic_api_key_configured": settings.anthropic_api_key_configured,
            },
        }

    @app.get("/api/runtime/state")
    async def get_runtime_state() -> RuntimeState:
        return session_manager.get_runtime_state()

    @app.get("/api/runtime/activity")
    async def get_runtime_activity() -> list[RuntimeActivityEntry]:
        return session_manager.list_activity()

    @app.get("/api/runtime/artifacts/{artifact_name}")
    async def read_runtime_artifact(artifact_name: str) -> dict[str, str]:
        try:
            return {
                "name": artifact_name,
                "content": session_manager.read_artifact(
                    session_manager.active_session_id,
                    artifact_name,
                ),
            }
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Artifact not found.") from exc

    @app.post("/api/runtime/upload")
    async def upload_file(file: UploadFile = File(...)) -> RuntimeState:
        content = await file.read()
        session_manager.store_upload(
            session_manager.active_session_id,
            file.filename or "uploaded-file",
            content,
        )
        return session_manager.get_runtime_state()

    @app.post("/api/runtime/chat")
    async def chat(payload: ChatRequest) -> ChatResponse:
        try:
            return await agent.run_turn(
                session_id=session_manager.active_session_id,
                message=payload.message,
                workflow=payload.workflow,
                skills=payload.skills,
            )
        except AgentRunError as exc:
            logger.exception("Agent runtime error during chat")
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during chat")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app
