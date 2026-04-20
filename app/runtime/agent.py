from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
import logging
import os
from pathlib import Path
from typing import Any, cast

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
    TextBlock,
    query,
)
from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

from app.core.config import Settings
from app.core.models import ChatResponse, UserFacingStatus, WorkflowType
from app.runtime.hooks import build_runtime_hooks
from app.runtime.mcp import build_runtime_mcp_config
from app.runtime.providers import resolve_claude_provider
from app.runtime.prompts import SYSTEM_PROMPT, build_turn_prompt
from app.session.manager import SessionManager
from app.transformation.governance import TransformationGovernancePolicy
from app.transformation.models import CapabilityId, TransformationExecutionPlan
from app.transformation.service import TransformationCapabilityService


logger = logging.getLogger(__name__)


class AgentRunError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


class ClaudeTransformationAgent:
    def __init__(
        self,
        settings: Settings,
        session_manager: SessionManager,
        capability_service: TransformationCapabilityService | None = None,
    ) -> None:
        self.settings = settings
        self.session_manager = session_manager
        self.capability_service = capability_service or TransformationCapabilityService()

    async def run_turn(
        self,
        session_id: str,
        message: str,
        workflow: WorkflowType,
        skills: list[str] | None = None,
    ) -> ChatResponse:
        plan = self.capability_service.plan_chat_turn(
            message=message,
            workflow=workflow,
            skills=skills,
        )
        return await self.run_execution_plan(session_id=session_id, plan=plan)

    async def stream_turn(
        self,
        session_id: str,
        message: str,
        workflow: WorkflowType,
        skills: list[str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        plan = self.capability_service.plan_chat_turn(
            message=message,
            workflow=workflow,
            skills=skills,
        )
        async for event in self.stream_execution_plan(session_id=session_id, plan=plan):
            yield event

    async def run_execution_plan(
        self,
        *,
        session_id: str,
        plan: TransformationExecutionPlan,
    ) -> ChatResponse:
        final_response: ChatResponse | None = None
        async for event in self.stream_execution_plan(session_id=session_id, plan=plan):
            if event["type"] == "final":
                final_response = cast(ChatResponse, event["response"])
        if final_response is None:
            raise AgentRunError("The agent run ended without returning a final response.")
        return final_response

    async def stream_execution_plan(
        self,
        *,
        session_id: str,
        plan: TransformationExecutionPlan,
    ) -> AsyncIterator[dict[str, Any]]:
        provider = resolve_claude_provider(self.settings)
        self._validate_runtime_configuration(provider.mode)
        session = self.session_manager.get_session(session_id)
        session_root = self.session_manager.session_root(session_id)
        uploaded_files = self.session_manager.list_uploaded_files(session_id)
        artifact_names = sorted(
            item.name
            for item in self.session_manager.list_artifacts(session_id)
            if item.kind == "artifact"
        )
        evidence_brief = self.capability_service.build_turn_brief(
            plan.objective,
            uploaded_files,
        )
        governance = TransformationGovernancePolicy(
            session_manager=self.session_manager,
            session_id=session_id,
        )

        prompt = build_turn_prompt(
            session_id=session_id,
            session_title=session.title,
            session_notes=session.notes,
            session_root=str(session_root),
            uploaded_files=uploaded_files,
            artifacts=artifact_names,
            workflow=plan.workflow,
            user_message=plan.objective,
            capabilities=plan.capabilities,
            surface=plan.surface,
            artifact_targets=plan.artifact_targets,
            evidence_brief=evidence_brief,
        )

        self.session_manager.append_message(
            session_id=session_id,
            role="user",
            content=plan.objective,
            workflow=plan.workflow,
            metadata={
                "skills": plan.skills,
                "capabilities": plan.capabilities,
                "surface": plan.surface,
            },
        )
        yield {
            "type": "status",
            "statuses": [
                status.model_dump(mode="json")
                for status in self.capability_service.build_user_facing_statuses(
                    plan.capabilities,
                    active=plan.capabilities[0] if plan.capabilities else None,
                )
            ],
            "detail": "Reviewing uploaded evidence and planning the next transformation step.",
            "detail_lines": [
                "I am using the session_context MCP server to inspect the uploaded evidence and current session state.",
                "I am planning which capabilities, skills, and artifact updates are needed for this transformation run.",
            ],
        }

        mcp_config = build_runtime_mcp_config(
            settings=self.settings,
            session_manager=self.session_manager,
            session_id=session_id,
        )

        stderr_lines: list[str] = []
        system_diagnostics: list[str] = []

        def handle_stderr(line: str) -> None:
            stderr_lines.append(line)
            logger.error("Claude CLI stderr: %s", line)
            self.session_manager.record_activity(
                event="claude-stderr",
                title="Claude CLI stderr",
                detail=line,
                level="warning",
            )

        options = ClaudeAgentOptions(
            cwd=str(self.settings.project_root),
            cli_path=self.settings.resolved_claude_cli_path,
            system_prompt=SYSTEM_PROMPT,
            setting_sources=["project"],
            skills=plan.skills,
            permission_mode=self.settings.runtime_permission_mode,
            tools=self._runtime_tools(),
            allowed_tools=[*self._runtime_tools(), *mcp_config.allowed_tools],
            mcp_servers=mcp_config.servers,
            hooks=build_runtime_hooks(
                governance=governance,
                session_root=session_root,
                audit_path=self.session_manager.audit_path,
                selected_capabilities=plan.capabilities,
            ),
            can_use_tool=self._build_tool_permission_callback(governance),
            plugins=[
                {
                    "type": "local",
                    "path": str(
                        self.settings.plugin_root / "transformation-delivery-helper"
                    ),
                }
            ],
            agents=self._subagents(),
            env=self._runtime_env(provider.env),
            effort="medium",
            max_turns=12,
            resume=session.sdk_session_id,
            stderr=handle_stderr,
            include_partial_messages=True,
        )

        latest_assistant_text = ""
        streamed_text = ""
        raw_result: str | None = None
        sdk_session_id = session.sdk_session_id
        result_error = False
        result_errors: list[str] = []

        try:
            async for message_item in query(
                prompt=self._streaming_prompt(prompt),
                options=options,
            ):
                if isinstance(message_item, TaskStartedMessage):
                    yield self._status_event_from_task_message(plan, message_item.description)
                elif isinstance(message_item, TaskProgressMessage):
                    detail = message_item.description
                    if message_item.last_tool_name:
                        detail = f"{detail} via {message_item.last_tool_name}"
                    yield self._status_event_from_task_message(plan, detail)
                elif isinstance(message_item, TaskNotificationMessage):
                    active = self._capability_for_runtime_text(plan, message_item.summary)
                    detail_lines = self._status_lines(plan, message_item.summary, active)
                    yield {
                        "type": "status",
                        "statuses": [
                            status.model_dump(mode="json")
                            for status in self.capability_service.build_user_facing_statuses(
                                plan.capabilities,
                                active=active,
                            )
                        ],
                        "detail": detail_lines[-1] if detail_lines else message_item.summary,
                        "detail_lines": detail_lines,
                    }
                elif isinstance(message_item, StreamEvent):
                    delta = self._text_delta_from_stream_event(message_item)
                    if delta:
                        streamed_text += delta
                        yield {"type": "delta", "text": delta}
                elif isinstance(message_item, SystemMessage):
                    if message_item.subtype == "init":
                        sdk_session_id = message_item.data.get("session_id", sdk_session_id)
                    else:
                        diagnostic = self._system_diagnostic(message_item)
                        if diagnostic:
                            system_diagnostics.append(diagnostic)
                elif isinstance(message_item, AssistantMessage):
                    current_text = "".join(
                        block.text
                        for block in message_item.content
                        if isinstance(block, TextBlock)
                    )
                    latest_assistant_text = current_text
                    if current_text.startswith(streamed_text):
                        delta = current_text[len(streamed_text) :]
                        if delta:
                            streamed_text = current_text
                            yield {"type": "delta", "text": delta}
                    for block in message_item.content:
                        if isinstance(block, TextBlock) and block.text:
                            latest_assistant_text = current_text
                elif isinstance(message_item, ResultMessage):
                    raw_result = message_item.result or raw_result
                    result_error = message_item.is_error
                    result_errors = message_item.errors or []
        except Exception as exc:  # noqa: BLE001
            stderr_tail = "\n".join(stderr_lines[-10:]).strip()
            system_tail = "\n".join(system_diagnostics[-5:]).strip()
            detail = str(exc).strip()
            if stderr_tail:
                detail = f"{detail}\n\nClaude CLI stderr:\n{stderr_tail}"
            if system_tail:
                detail = f"{detail}\n\nClaude system diagnostics:\n{system_tail}"
            self.session_manager.record_activity(
                event="agent-run-failed",
                title="Agent run failed",
                detail=detail or exc.__class__.__name__,
                level="error",
                metadata={
                    "workflow": plan.workflow,
                    "capabilities": plan.capabilities,
                    "provider_mode": provider.mode,
                },
            )
            raise AgentRunError(detail or exc.__class__.__name__) from exc

        if sdk_session_id and sdk_session_id != session.sdk_session_id:
            session = self.session_manager.set_sdk_session_id(session_id, sdk_session_id)
        else:
            session = self.session_manager.get_session(session_id)

        reply = (raw_result or latest_assistant_text).strip()
        if result_error:
            if result_errors:
                reply = f"{reply}\n\nErrors:\n- " + "\n- ".join(result_errors)
            if not reply:
                reply = "The agent run failed before a final answer was produced."

        self.session_manager.append_message(
            session_id=session_id,
            role="assistant",
            content=reply,
            workflow=plan.workflow,
            metadata={
                "raw_result": raw_result,
                "skills": plan.skills,
                "capabilities": plan.capabilities,
                "surface": plan.surface,
            },
        )
        self._synchronize_derived_outputs(session_id)

        runtime_state = self.session_manager.get_runtime_state()
        final_response = ChatResponse(
            session=runtime_state.session,
            reply=reply,
            workflow=plan.workflow,
            artifacts=runtime_state.artifacts,
            uploads=runtime_state.uploads,
            outputs=runtime_state.outputs,
            activity=runtime_state.activity,
            statuses=self._final_statuses(plan, reply),
            sdk_session_id=sdk_session_id,
            raw_result=raw_result,
        )
        yield {
            "type": "final",
            "response": final_response,
        }

    def _synchronize_derived_outputs(self, session_id: str) -> None:
        summary_content = self.session_manager.build_merged_artifact_summary(session_id)
        self.session_manager.upsert_output(
            session_id,
            "transformation_summary.md",
            summary_content,
            description="Merged summary across the session artifact documents.",
        )
        readme_content = self.session_manager.build_output_readme(session_id)
        self.session_manager.upsert_output(
            session_id,
            "transformation_readme.md",
            readme_content,
            description="Usage guidance for the generated transformation outputs.",
        )

    def _runtime_tools(self) -> list[str]:
        tools = ["Read", "Glob", "Grep", "Skill", "Agent"]
        if self.settings.enable_direct_file_tools:
            tools.extend(["Write", "Edit"])
        return tools

    def _streaming_prompt(self, prompt: str) -> AsyncIterable[dict[str, Any]]:
        async def prompt_stream() -> AsyncIterator[dict[str, Any]]:
            yield {
                "type": "user",
                "session_id": "default",
                "message": {
                    "role": "user",
                    "content": prompt,
                },
                "parent_tool_use_id": None,
            }

        return prompt_stream()

    def _runtime_env(self, provider_env: dict[str, str]) -> dict[str, str]:
        claude_config_dir = self._claude_config_dir()
        claude_config_dir.mkdir(parents=True, exist_ok=True)
        env = dict(provider_env)
        env["CLAUDE_CONFIG_DIR"] = str(claude_config_dir)
        return env

    def _claude_config_dir(self) -> Path:
        return self.settings.storage_root / ".claude-runtime"

    def _system_diagnostic(self, message_item: SystemMessage) -> str | None:
        data = getattr(message_item, "data", {}) or {}

        if message_item.subtype == "hook_response" and data.get("outcome") == "error":
            hook_name = data.get("hook_name", "unknown hook")
            detail = data.get("stderr") or data.get("output") or "Hook failed without stderr."
            diagnostic = f"{hook_name}: {detail}"
            self.session_manager.record_activity(
                event="claude-hook-error",
                title=f"Claude hook failed: {hook_name}",
                detail=detail,
                level="warning",
            )
            return diagnostic

        if message_item.subtype == "api_retry":
            attempt = data.get("attempt", "?")
            max_retries = data.get("max_retries", "?")
            reason = data.get("error_status") or data.get("error") or "unknown"
            diagnostic = f"API retry {attempt}/{max_retries}: {reason}"
            self.session_manager.record_activity(
                event="claude-api-retry",
                title=f"Claude API retry {attempt}/{max_retries}",
                detail=f"Claude Code reported a retry because of: {reason}.",
                level="warning",
            )
            return diagnostic

        return None

    def _validate_runtime_configuration(self, provider_mode: str) -> None:
        if not self.settings.resolved_claude_cli_path:
            self.session_manager.record_activity(
                event="runtime-error",
                title="Claude Code CLI missing",
                detail="Install the `claude` CLI or set CLAUDE_CLI_PATH in .env to the correct binary path.",
                level="error",
            )
            raise AgentRunError(
                "Claude Code CLI was not found. Install the `claude` CLI or set "
                "`CLAUDE_CLI_PATH` in `.env` to the correct binary path.",
                status_code=503,
            )
        if provider_mode == "anthropic" and not self.settings.anthropic_api_key_configured:
            self.session_manager.record_activity(
                event="runtime-warning",
                title="ANTHROPIC_API_KEY not set",
                detail="If Claude Code is not already authenticated locally, add ANTHROPIC_API_KEY to .env before chatting.",
                level="warning",
            )
        if provider_mode in {"bedrock", "mantle"} and not (
            self.settings.aws_region or os.environ.get("AWS_REGION", "").strip()
        ):
            self.session_manager.record_activity(
                event="runtime-warning",
                title="AWS region not configured",
                detail="Bedrock mode is enabled but AWS_REGION is not set.",
                level="warning",
            )

    def _subagents(self) -> dict[str, AgentDefinition]:
        mcp_servers: list[str | dict[str, Any]] = [
            "session_artifacts",
            "session_context",
        ]
        mcp_tools = [
            "mcp__session_artifacts__*",
            "mcp__session_context__*",
        ]
        if self.settings.local_insights_mcp_enabled:
            mcp_servers.append("local_insights")
            mcp_tools.append("mcp__local_insights__*")
        return {
            "source-analyst": AgentDefinition(
                description="Use for clarifying source material, target contracts, missing inputs, and transformation assumptions.",
                prompt=(
                    "Focus on source analysis and target contract interpretation. Pull out the concrete transformation objective, "
                    "key ambiguities, and what still needs clarification. Improve the transformation-understanding artifact."
                ),
                tools=[
                    "Read",
                    "Glob",
                    "Grep",
                    "Skill",
                    *mcp_tools,
                ],
                skills=["source-analysis", "target-contract-analysis"],
                mcpServers=mcp_servers,
                permissionMode=self.settings.runtime_permission_mode,
            ),
            "lineage-analyst": AgentDefinition(
                description="Use for lineage, dependencies, sequencing, joins, validation points, and data movement dependencies.",
                prompt=(
                    "Focus on mapping rules, upstream and downstream dependencies, required joins, sequencing, lineage, validation, and operational risk. "
                    "Improve the transformation understanding and dependency artifacts."
                ),
                tools=[
                    "Read",
                    "Glob",
                    "Grep",
                    "Skill",
                    *mcp_tools,
                ],
                skills=["mapping-and-rules", "dependency-and-lineage"],
                mcpServers=mcp_servers,
                permissionMode=self.settings.runtime_permission_mode,
            ),
            "delivery-readiness-planner": AgentDefinition(
                description="Use for delivery planning, authority checkpoints, packaging, implementation steps, and Python-first output design.",
                prompt=(
                    "Focus on implementation generation, validation and reconciliation, delivery readiness, and approval evidence. "
                    "Shape practical Python-first implementation outputs while keeping room for other target artifacts later."
                ),
                tools=[
                    "Read",
                    "Glob",
                    "Grep",
                    "Skill",
                    *mcp_tools,
                ],
                skills=[
                    "implementation-generation",
                    "validation-and-reconciliation",
                    "delivery-readiness",
                    "transformation-delivery-helper:approval-and-evidence",
                ],
                mcpServers=mcp_servers,
                permissionMode=self.settings.runtime_permission_mode,
            ),
        }

    def _status_event_from_task_message(
        self,
        plan: TransformationExecutionPlan,
        detail: str,
    ) -> dict[str, Any]:
        active = self._capability_for_runtime_text(plan, detail)
        detail_lines = self._status_lines(plan, detail, active)
        return {
            "type": "status",
            "statuses": [
                status.model_dump(mode="json")
                for status in self.capability_service.build_user_facing_statuses(
                    plan.capabilities,
                    active=active,
                )
            ],
            "detail": detail_lines[-1] if detail_lines else self._friendly_status_detail(detail, active),
            "detail_lines": detail_lines,
        }

    def _capability_for_runtime_text(
        self,
        plan: TransformationExecutionPlan,
        text: str | None,
    ) -> CapabilityId | None:
        detail = (text or "").lower()
        if any(token in detail for token in ("source", "upload", "read_session_upload", "describe_session_context")):
            return "source_analysis" if "source_analysis" in plan.capabilities else plan.capabilities[0]
        if any(token in detail for token in ("target", "contract", "schema", "ddl")):
            return "target_contract_analysis" if "target_contract_analysis" in plan.capabilities else plan.capabilities[0]
        if any(token in detail for token in ("mapping", "rule", "field")):
            return "mapping_and_rules" if "mapping_and_rules" in plan.capabilities else plan.capabilities[0]
        if any(token in detail for token in ("lineage", "dependency", "join")):
            return "dependency_and_lineage" if "dependency_and_lineage" in plan.capabilities else plan.capabilities[0]
        if any(token in detail for token in ("validation", "reconciliation", "test")):
            return "validation_and_reconciliation" if "validation_and_reconciliation" in plan.capabilities else plan.capabilities[0]
        if any(token in detail for token in ("output", "deliver", "artifact", "write_session_output")):
            return "delivery_readiness" if "delivery_readiness" in plan.capabilities else plan.capabilities[0]
        if any(token in detail for token in ("approval", "evidence", "sign-off")):
            return "approval_and_evidence" if "approval_and_evidence" in plan.capabilities else plan.capabilities[0]
        if any(token in detail for token in ("python", "implementation", "code")):
            return "implementation_generation" if "implementation_generation" in plan.capabilities else plan.capabilities[0]
        return plan.capabilities[0] if plan.capabilities else None

    def _friendly_status_detail(
        self,
        detail: str,
        active: CapabilityId | None,
    ) -> str:
        capability_details: dict[CapabilityId, str] = {
            "source_analysis": "Understanding source structure and uploaded evidence.",
            "target_contract_analysis": "Checking target requirements and contract details.",
            "mapping_and_rules": "Mapping fields and business rules.",
            "dependency_and_lineage": "Tracing dependencies and lineage.",
            "implementation_generation": "Generating transformation implementation output.",
            "validation_and_reconciliation": "Checking validation and reconciliation needs.",
            "delivery_readiness": "Preparing deliverables and session outputs.",
            "approval_and_evidence": "Reviewing evidence, assumptions, and approval needs.",
        }
        if active in capability_details:
            return capability_details[active]
        cleaned = detail.replace("mcp__", "").replace("__", " / ")
        return cleaned[:220]

    def _status_lines(
        self,
        plan: TransformationExecutionPlan,
        detail: str,
        active: CapabilityId | None,
    ) -> list[str]:
        lower = detail.lower()
        lines: list[str] = []
        capability_line = self._friendly_status_detail(detail, active)
        if capability_line:
            lines.append(capability_line)

        if any(token in lower for token in ("describe_session_context", "read_session_upload", "session_context")):
            lines.append("I am using the session_context MCP server to inspect uploads, session context, or template blueprints.")
        if any(token in lower for token in ("read_template_blueprint", "list_template_blueprints", "template")):
            lines.append("I am reading the current artifact blueprint structure so the markdown stays aligned with the templates.")
        if "write_session_artifact" in lower or "session_artifacts" in lower:
            lines.append("I am using the session_artifacts MCP server to update the governed session artifact files.")
        if "write_session_output" in lower:
            lines.append("I am using the session_artifacts MCP server to write generated deliverables into the outputs folder.")
        if "local_insights" in lower:
            lines.append("I am using the local_insights MCP server to inspect runtime or repository diagnostics.")
        if "hook" in lower:
            lines.append("A runtime hook is checking whether the requested mutation is allowed.")

        skill_lines = {
            "source-analysis": "Using the source-analysis skill to understand the uploaded source evidence.",
            "target-contract-analysis": "Using the target-contract-analysis skill to clarify the target contract.",
            "mapping-and-rules": "Using the mapping-and-rules skill to formalise field mappings and business rules.",
            "dependency-and-lineage": "Using the dependency-and-lineage skill to capture joins, dependencies, and lineage.",
            "implementation-generation": "Using the implementation-generation skill to shape the transformation implementation.",
            "validation-and-reconciliation": "Using the validation-and-reconciliation skill to define checks and reconciliation steps.",
            "delivery-readiness": "Using the delivery-readiness skill to package the final deliverables and operational notes.",
            "approval-and-evidence": "Using the approval-and-evidence skill to capture evidence and approval requirements.",
        }
        for token, message in skill_lines.items():
            if token in lower:
                lines.append(message.replace("Using", "I am using"))

        artifact_messages = {
            "transformation-understanding.md": "Updating `transformation-understanding.md` with the latest transformation context.",
            "data-dependency-map.md": "Updating `data-dependency-map.md` with dependencies, controls, and lineage details.",
            "delivery-implementation-plan.md": "Updating `delivery-implementation-plan.md` with implementation and delivery planning detail.",
        }
        for artifact_name, message in artifact_messages.items():
            if artifact_name in lower:
                lines.append(message.replace("Updating", "I am updating"))

        deduped: list[str] = []
        for line in lines:
            if line and line not in deduped:
                deduped.append(line)
        if not deduped:
            deduped.append(plan.objective[:220])
        return deduped

    def _text_delta_from_stream_event(self, event: StreamEvent) -> str:
        payload = event.event or {}
        if payload.get("type") != "content_block_delta":
            return ""
        delta = payload.get("delta", {})
        if delta.get("type") != "text_delta":
            return ""
        text = delta.get("text")
        return text if isinstance(text, str) else ""

    def _final_statuses(
        self,
        plan: TransformationExecutionPlan,
        reply: str,
    ) -> list[UserFacingStatus]:
        blocked_reason = None
        reply_lower = reply.lower()
        if "missing required inputs" in reply_lower or "need the following" in reply_lower:
            blocked_reason = "Additional source or target evidence is still needed."
        statuses = self.capability_service.build_user_facing_statuses(
            plan.capabilities,
            blocked_reason=blocked_reason,
        )
        if blocked_reason is None:
            for status in statuses:
                status.state = "done"
        return statuses

    def _build_tool_permission_callback(
        self,
        governance: TransformationGovernancePolicy,
    ) -> Any:
        allowed_roots = [path.resolve() for path in governance.allowed_direct_write_roots()]
        protected_roots = [path.resolve() for path in governance.protected_session_roots()]

        async def can_use_tool(
            tool_name: str,
            tool_input: dict[str, Any],
            _context: ToolPermissionContext,
        ) -> PermissionResultAllow | PermissionResultDeny:
            if tool_name not in {"Write", "Edit"}:
                return cast(PermissionResultAllow, {"behavior": "allow"})

            file_path = tool_input.get("file_path")
            if not isinstance(file_path, str) or not file_path:
                return cast(PermissionResultAllow, {"behavior": "allow"})

            candidate = Path(file_path)
            if not candidate.is_absolute():
                candidate = self.settings.project_root / candidate
            candidate = candidate.resolve()

            if any(candidate.is_relative_to(root) for root in allowed_roots):
                return cast(PermissionResultAllow, {"behavior": "allow"})

            if any(candidate.is_relative_to(root) for root in protected_roots):
                return cast(
                    PermissionResultDeny,
                    {
                        "behavior": "deny",
                        "message": (
                            "Direct edits to uploads, artifacts, and outputs are blocked. "
                            "Use the session_artifacts MCP tools so the session history stays auditable."
                        ),
                        "interrupt": False,
                    },
                )

            if candidate.is_relative_to(governance.session_manager.session_root(governance.session_id)):
                return cast(
                    PermissionResultDeny,
                    {
                        "behavior": "deny",
                        "message": (
                            "Direct edits inside the session workspace are limited to workspace/scratch. "
                            "Use MCP tools for artifacts and outputs."
                        ),
                        "interrupt": False,
                    },
                )

            return cast(PermissionResultAllow, {"behavior": "allow"})

        return can_use_tool
