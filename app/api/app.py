from __future__ import annotations

import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.core.auth import AUTH_COOKIE_NAME, is_authenticated_cookie
from app.core.config import get_settings
from app.core.models import (
    ArtifactKind,
    ChatRequest,
    ChatResponse,
    RuntimeActivityEntry,
    RuntimeState,
    UserFacingStatus,
)
from app.runtime.agent import AgentRunError, ClaudeTransformationAgent
from app.runtime.providers import resolve_claude_provider
from app.session.manager import SessionManager
from app.transformation.models import (
    CapabilityId,
    StructuredTransformationRequest,
    StructuredTransformationResponse,
)
from app.transformation.service import TransformationCapabilityService


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    session_manager = SessionManager(
        sessions_root=settings.sessions_root,
        templates_root=settings.templates_root,
    )
    capability_service = TransformationCapabilityService()
    agent = ClaudeTransformationAgent(
        settings=settings,
        session_manager=session_manager,
        capability_service=capability_service,
    )

    def allowed_ui_origins() -> list[str]:
        origins = {
            f"http://{settings.ui_host}:{settings.ui_port}",
            settings.resolved_backend_url,
        }
        local_aliases = {"127.0.0.1", "localhost"}
        if settings.ui_host in local_aliases:
            for host in local_aliases:
                origins.add(f"http://{host}:{settings.ui_port}")
        for host in local_aliases:
            origins.add(f"http://{host}:{settings.api_port}")
        return sorted(origins)

    allowed_origins = set(allowed_ui_origins())

    app = FastAPI(
        title="Data Transformation Agent API",
        version="0.2.0",
        description="FastAPI backend for the Data Transformation capability platform and its Claude runtime surface.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_ui_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def require_login(request: Any, call_next: Any) -> Any:
        if request.method == "OPTIONS" or request.url.path == "/health":
            return await call_next(request)
        if is_authenticated_cookie(request.cookies.get(AUTH_COOKIE_NAME), settings):
            return await call_next(request)
        response = JSONResponse(status_code=401, content={"detail": "Authentication required."})
        origin = request.headers.get("origin")
        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        return response

    ability_catalog = capability_service.list_runtime_abilities()
    ability_index = {
        item.slash.lstrip("/").lower(): item
        for item in ability_catalog
    }
    ability_index.update(
        {
            item.workflow.lower(): item
            for item in ability_catalog
        }
    )
    ability_index.update(
        {
            item.label.lower().replace(" ", "-"): item
            for item in ability_catalog
        }
    )

    default_ability = next((item for item in ability_catalog if item.slash == "/agent"), ability_catalog[0])
    configured_modes = settings.ui_exposed_modes_list
    if not configured_modes:
        configured_modes = [default_ability.slash.lstrip("/")]

    exposed_abilities: list[Any] = []
    if settings.ui_show_mode_picker:
        seen_slashes: set[str] = set()
        for mode in configured_modes:
            ability = ability_index.get(mode.lower().lstrip("/"))
            if ability and ability.slash not in seen_slashes:
                exposed_abilities.append(ability)
                seen_slashes.add(ability.slash)
    if not exposed_abilities:
        exposed_abilities = [default_ability]

    developer_subagents = [
        {
            "id": "source-analyst",
            "label": "Source Specialist",
            "description": "Focused on source structure, anomalies, and field semantics.",
        },
        {
            "id": "lineage-analyst",
            "label": "Lineage Specialist",
            "description": "Focused on lineage, dependencies, reconciliation, and operational controls.",
        },
        {
            "id": "delivery-readiness-planner",
            "label": "Delivery Specialist",
            "description": "Focused on implementation readiness, packaging, and delivery evidence.",
        },
    ]
    configured_subagents = {item.lower() for item in settings.ui_exposed_subagents_list}
    exposed_subagents = [
        item
        for item in developer_subagents
        if settings.ui_show_subagents
        and (not configured_subagents or item["id"].lower() in configured_subagents)
    ]
    suggested_prompts = [
        "Map this CSV customer extract to the uploaded target contract and list anything still missing.",
        "Use the uploaded business rules to draft the transformation logic and validation approach.",
        "Review these files and tell me which final deliverables you can generate now versus what is blocked.",
    ]
    sample_tests_root = settings.project_root / "test" / "sampletestdata"

    def reset_runtime() -> None:
        nonlocal session_manager, agent
        session_manager = SessionManager(
            sessions_root=settings.sessions_root,
            templates_root=settings.templates_root,
        )
        agent = ClaudeTransformationAgent(
            settings=settings,
            session_manager=session_manager,
            capability_service=capability_service,
        )

    def list_sample_case_dirs() -> list[Path]:
        if not sample_tests_root.exists():
            return []
        return sorted(path for path in sample_tests_root.iterdir() if path.is_dir())

    def resolve_sample_case(case_name: str) -> Path:
        for case_dir in list_sample_case_dirs():
            if case_dir.name == case_name:
                return case_dir
        raise FileNotFoundError(case_name)

    def build_missing_information_summary() -> str:
        return session_manager.build_merged_artifact_summary(session_manager.active_session_id)

    async def execute_structured(
        payload: StructuredTransformationRequest,
        capability_override: CapabilityId | None = None,
    ) -> StructuredTransformationResponse:
        session_id = payload.session_id or session_manager.active_session_id
        plan = capability_service.plan_structured_request(
            payload,
            capability_override=capability_override,
            surface="api",
        )
        result = await agent.run_execution_plan(session_id=session_id, plan=plan)
        return StructuredTransformationResponse(
            capability=capability_override,
            capabilities=plan.capabilities,
            workflow=plan.workflow,
            skills=plan.skills,
            prompt_objective=plan.objective,
            reply=result.reply,
            raw_result=result.raw_result,
            session_id=result.session.id,
            artifacts=[item.path for item in result.artifacts],
            outputs=[item.path for item in result.outputs],
        )

    async def execute_structured_or_500(
        payload: StructuredTransformationRequest,
        capability_override: CapabilityId | None = None,
    ) -> StructuredTransformationResponse:
        try:
            return await execute_structured(payload, capability_override)
        except AgentRunError as exc:
            logger.exception("Agent runtime error during structured execution")
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during structured execution")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runtime/capabilities")
    async def runtime_capabilities() -> dict[str, Any]:
        provider = resolve_claude_provider(settings)
        all_abilities = [item.model_dump(mode="json") for item in ability_catalog]
        user_abilities = [item.model_dump(mode="json") for item in exposed_abilities]
        internal_mcp_servers = [
            {
                "name": "session_artifacts",
                "transport": "sdk",
                "allowed_tool_glob": "mcp__session_artifacts__*",
                "purpose": "Governed session artifact and output writes for the active runtime.",
            },
            {
                "name": "session_context",
                "transport": "sdk",
                "allowed_tool_glob": "mcp__session_context__*",
                "purpose": "Runtime session metadata, uploads, and artifact blueprint context.",
            },
        ]
        if settings.local_insights_mcp_enabled:
            internal_mcp_servers.append(
                {
                    "name": "local_insights",
                    "transport": "stdio",
                    "allowed_tool_glob": "mcp__local_insights__*",
                    "purpose": "Runtime and repository diagnostics exposed through a separate MCP process.",
                }
            )
        if settings.github_mcp_enabled and settings.github_token:
            internal_mcp_servers.append(
                {
                    "name": "github",
                    "transport": "stdio",
                    "allowed_tool_glob": "mcp__github__*",
                    "purpose": "Optional GitHub MCP integration configured from environment variables.",
                }
            )
        if settings.remote_mcp_enabled and settings.remote_mcp_url:
            internal_mcp_servers.append(
                {
                    "name": settings.remote_mcp_name,
                    "transport": settings.remote_mcp_type,
                    "allowed_tool_glob": f"mcp__{settings.remote_mcp_name}__*",
                    "purpose": "Optional remote MCP integration configured from environment variables.",
                }
            )

        alerts: list[dict[str, str]] = []
        if not settings.resolved_claude_cli_path:
            alerts.append(
                {
                    "level": "warning",
                    "title": "Claude CLI not found",
                    "detail": "Install or point the runtime to the Claude CLI before starting a chat run.",
                }
            )
        if provider.mode == "anthropic" and not settings.anthropic_api_key_configured:
            alerts.append(
                {
                    "level": "warning",
                    "title": "Provider access is incomplete",
                    "detail": "Set ANTHROPIC_API_KEY or choose another configured Claude provider mode.",
                }
            )

        return {
            "session_mode": "ephemeral-runtime",
            "tool_search": {"ENABLE_TOOL_SEARCH": "auto:5"},
            "skills": sorted(
                {
                    capability["default_skill"]
                    for capability in (
                        item.model_dump(mode="json") for item in capability_service.list_capabilities()
                    )
                }
            ),
            "abilities": user_abilities,
            "all_abilities": all_abilities,
            "capabilities": [item.model_dump(mode="json") for item in capability_service.list_capabilities()],
            "subagents": [item["id"] for item in developer_subagents],
            "mcp_servers": {
                "internal_runtime": internal_mcp_servers,
                "external_domain": {
                    "name": "transformation_domain",
                    "transport": "stdio",
                    "script": str(settings.project_root / "scripts" / "mcp" / "transformation_domain_server.py"),
                    "tools": [
                        "analyse_source",
                        "interpret_target_contract",
                        "generate_mapping_rules",
                        "generate_transform_code",
                        "generate_validation_plan",
                        "prepare_delivery_pack",
                        "assess_approval_requirements",
                    ],
                },
            },
            "api_surfaces": {
                "chat": "/api/runtime/chat",
                "chat_stream": "/api/runtime/chat/stream",
                "execute": "/api/transformation/execute",
                "capabilities": "/api/transformation/capabilities",
            },
            "friendly_status_catalog": [
                item.model_dump(mode="json")
                for item in capability_service.build_user_facing_statuses(
                    capability_service.default_capabilities_for_workflow("general")
                )
            ],
            "ui": {
                "show_developer_panel": settings.ui_show_developer_panel,
                "show_mode_picker": settings.ui_show_mode_picker,
                "show_subagents": settings.ui_show_subagents,
                "show_document_panel": settings.ui_show_document_panel,
                "show_suggested_prompts": settings.ui_show_suggested_prompts,
                "suggested_prompts": suggested_prompts if settings.ui_show_suggested_prompts else [],
                "modes": user_abilities,
                "subagents": exposed_subagents,
                "primary_agent": {
                    "label": "Transformation Agent",
                    "description": "Chat with one evidence-aware agent that decides which internal capabilities to use.",
                },
            },
            "alerts": alerts,
            "runtime": {
                "session_id": session_manager.active_session_id,
                "ready": bool(settings.resolved_claude_cli_path)
                and (provider.mode != "anthropic" or settings.anthropic_api_key_configured),
                "provider": provider.status | {"label": provider.label},
                "claude_cli_available": bool(settings.resolved_claude_cli_path),
                "claude_cli_path": settings.resolved_claude_cli_path or settings.claude_cli_path,
                "anthropic_api_key_configured": settings.anthropic_api_key_configured,
                "permission_mode": settings.runtime_permission_mode,
                "direct_file_tools_enabled": settings.enable_direct_file_tools,
            },
            "developer": {
                "skills": sorted(
                    {
                        capability["default_skill"]
                        for capability in (
                            item.model_dump(mode="json") for item in capability_service.list_capabilities()
                        )
                    }
                ),
                "subagents": developer_subagents,
                "mcp_servers": {
                    "internal_runtime": internal_mcp_servers,
                    "external_domain": {
                        "name": "transformation_domain",
                        "transport": "stdio",
                        "script": str(settings.project_root / "scripts" / "mcp" / "transformation_domain_server.py"),
                        "tools": [
                            "analyse_source",
                            "interpret_target_contract",
                            "generate_mapping_rules",
                            "generate_transform_code",
                            "generate_validation_plan",
                            "prepare_delivery_pack",
                            "assess_approval_requirements",
                        ],
                    },
                },
                "runtime": {
                    "session_id": session_manager.active_session_id,
                    "claude_cli_available": bool(settings.resolved_claude_cli_path),
                    "claude_cli_path": settings.resolved_claude_cli_path or settings.claude_cli_path,
                    "anthropic_api_key_configured": settings.anthropic_api_key_configured,
                    "provider": provider.status | {"label": provider.label},
                    "permission_mode": settings.runtime_permission_mode,
                    "direct_file_tools_enabled": settings.enable_direct_file_tools,
                },
            },
        }

    @app.get("/api/runtime/state")
    async def get_runtime_state() -> RuntimeState:
        return session_manager.get_runtime_state()

    @app.post("/api/runtime/reset")
    async def reset_runtime_state() -> RuntimeState:
        reset_runtime()
        return session_manager.get_runtime_state()

    @app.get("/api/runtime/activity")
    async def get_runtime_activity() -> list[RuntimeActivityEntry]:
        return session_manager.list_activity()

    @app.get("/api/runtime/missing-information-summary")
    async def missing_information_summary() -> Response:
        content = build_missing_information_summary()
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="transformation_summary.md"'
            },
        )

    @app.get("/api/runtime/test-cases")
    async def list_runtime_test_cases() -> dict[str, Any]:
        cases = list_sample_case_dirs()
        return {
            "cases": [
                {
                    "id": case_dir.name,
                    "label": f"Test {index}",
                    "name": case_dir.name,
                }
                for index, case_dir in enumerate(cases, start=1)
            ]
        }

    @app.get("/api/runtime/test-cases/{case_name}")
    async def get_runtime_test_case(case_name: str) -> dict[str, Any]:
        try:
            case_dir = resolve_sample_case(case_name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Test case not found.") from exc

        request_path = case_dir / "chat_request.txt"
        if not request_path.exists() or not request_path.is_file():
            raise HTTPException(status_code=400, detail="Test case is missing chat_request.txt.")

        files: list[dict[str, str]] = []
        for path in sorted(case_dir.iterdir()):
            if not path.is_file() or path.name == "chat_request.txt":
                continue
            files.append(
                {
                    "name": path.name,
                    "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
                }
            )

        return {
            "id": case_dir.name,
            "request_text": request_path.read_text(encoding="utf-8"),
            "files": files,
        }

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

    @app.get("/api/runtime/files/{kind}/{asset_name}")
    async def download_runtime_file(kind: ArtifactKind, asset_name: str) -> FileResponse:
        try:
            path = session_manager.resolve_asset_path(
                session_manager.active_session_id,
                kind,
                asset_name,
            )
            return FileResponse(path, filename=path.name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="File not found.") from exc

    @app.post("/api/runtime/chat")
    async def chat(payload: ChatRequest) -> ChatResponse:
        try:
            response = await agent.run_turn(
                session_id=session_manager.active_session_id,
                message=payload.message,
                workflow=payload.workflow,
                skills=payload.skills,
            )
            session_manager.set_statuses(response.statuses)
            return response
        except AgentRunError as exc:
            logger.exception("Agent runtime error during chat")
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during chat")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/runtime/chat/stream")
    async def chat_stream(payload: ChatRequest) -> StreamingResponse:
        async def event_stream() -> Any:
            try:
                async for event in agent.stream_turn(
                    session_id=session_manager.active_session_id,
                    message=payload.message,
                    workflow=payload.workflow,
                    skills=payload.skills,
                ):
                    event_type = event.get("type")
                    if event_type == "status":
                        statuses = [
                            UserFacingStatus.model_validate(item)
                            for item in cast(list[dict[str, Any]], event.get("statuses", []))
                        ]
                        session_manager.set_statuses(statuses)
                    elif event_type == "final":
                        response = cast(ChatResponse, event["response"])
                        session_manager.set_statuses(response.statuses)
                        yield json.dumps(
                            {
                                "type": "final",
                                "response": response.model_dump(mode="json"),
                                "runtime_state": session_manager.get_runtime_state().model_dump(mode="json"),
                            }
                        ) + "\n"
                        return
                    yield json.dumps(event) + "\n"
            except AgentRunError as exc:
                logger.exception("Agent runtime error during streamed chat")
                yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected error during streamed chat")
                yield json.dumps({"type": "error", "detail": str(exc)}) + "\n"

        return StreamingResponse(event_stream(), media_type="application/x-ndjson")

    @app.get("/api/transformation/capabilities")
    async def transformation_capabilities() -> dict[str, Any]:
        return {
            "capabilities": [item.model_dump(mode="json") for item in capability_service.list_capabilities()],
            "abilities": [item.model_dump(mode="json") for item in exposed_abilities],
            "primary_surface": "/agent",
        }

    @app.post("/api/transformation/execute")
    async def execute_transformation(
        payload: StructuredTransformationRequest,
    ) -> StructuredTransformationResponse:
        return await execute_structured_or_500(payload)

    @app.post("/api/transformation/source-analysis")
    async def source_analysis(
        payload: StructuredTransformationRequest,
    ) -> StructuredTransformationResponse:
        return await execute_structured_or_500(payload, capability_override="source_analysis")

    @app.post("/api/transformation/target-contract-analysis")
    async def target_contract_analysis(
        payload: StructuredTransformationRequest,
    ) -> StructuredTransformationResponse:
        return await execute_structured_or_500(payload, capability_override="target_contract_analysis")

    @app.post("/api/transformation/mapping-rules")
    async def mapping_rules(
        payload: StructuredTransformationRequest,
    ) -> StructuredTransformationResponse:
        return await execute_structured_or_500(payload, capability_override="mapping_and_rules")

    @app.post("/api/transformation/implementation")
    async def implementation_generation(
        payload: StructuredTransformationRequest,
    ) -> StructuredTransformationResponse:
        return await execute_structured_or_500(payload, capability_override="implementation_generation")

    @app.post("/api/transformation/validation-plan")
    async def validation_plan(
        payload: StructuredTransformationRequest,
    ) -> StructuredTransformationResponse:
        return await execute_structured_or_500(
            payload,
            capability_override="validation_and_reconciliation",
        )

    @app.post("/api/transformation/delivery-pack")
    async def delivery_pack(
        payload: StructuredTransformationRequest,
    ) -> StructuredTransformationResponse:
        return await execute_structured_or_500(payload, capability_override="delivery_readiness")

    @app.post("/api/transformation/approval-requirements")
    async def approval_requirements(
        payload: StructuredTransformationRequest,
    ) -> StructuredTransformationResponse:
        return await execute_structured_or_500(payload, capability_override="approval_and_evidence")

    return app
