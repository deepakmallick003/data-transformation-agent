from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    query,
)

from app.core.config import Settings
from app.core.models import ChatResponse, WorkflowType
from app.runtime.hooks import build_runtime_hooks
from app.runtime.mcp import build_runtime_mcp_config
from app.runtime.prompts import SYSTEM_PROMPT, build_turn_prompt
from app.session.manager import SessionManager


logger = logging.getLogger(__name__)


class AgentRunError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


class ClaudeTransformationAgent:
    def __init__(self, settings: Settings, session_manager: SessionManager) -> None:
        self.settings = settings
        self.session_manager = session_manager

    async def run_turn(
        self,
        session_id: str,
        message: str,
        workflow: WorkflowType,
        skills: list[str] | None = None,
    ) -> ChatResponse:
        self._validate_runtime_configuration()
        session = self.session_manager.get_session(session_id)
        session_root = self.session_manager.session_root(session_id)
        uploaded_files = self.session_manager.list_uploaded_files(session_id)
        artifact_names = sorted(
            item.name
            for item in self.session_manager.list_artifacts(session_id)
            if item.kind == "artifact"
        )

        prompt = build_turn_prompt(
            session_id=session_id,
            session_title=session.title,
            session_notes=session.notes,
            session_root=str(session_root),
            uploaded_files=uploaded_files,
            artifacts=artifact_names,
            workflow=workflow,
            user_message=message,
        )

        self.session_manager.append_message(
            session_id=session_id,
            role="user",
            content=message,
            workflow=workflow,
            metadata={"skills": skills or self._default_skills()},
        )

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
            skills=skills or self._default_skills(),
            permission_mode="acceptEdits",
            tools=["Read", "Write", "Edit", "Glob", "Grep", "Skill", "Agent"],
            allowed_tools=[
                "Read",
                "Write",
                "Edit",
                "Glob",
                "Grep",
                "Skill",
                "Agent",
                *mcp_config.allowed_tools,
            ],
            mcp_servers=mcp_config.servers,
            hooks=build_runtime_hooks(
                session_root=session_root,
                audit_path=self.session_manager.audit_path,
            ),
            plugins=[
                {
                    "type": "local",
                    "path": str(
                        self.settings.plugin_root / "transformation-delivery-helper"
                    ),
                }
            ],
            agents=self._subagents(),
            env=self._runtime_env(),
            effort="medium",
            max_turns=12,
            resume=session.sdk_session_id,
            stderr=handle_stderr,
        )

        assistant_text: list[str] = []
        raw_result: str | None = None
        sdk_session_id = session.sdk_session_id
        result_error = False
        result_errors: list[str] = []

        try:
            async for message_item in query(prompt=prompt, options=options):
                if isinstance(message_item, SystemMessage):
                    if message_item.subtype == "init":
                        sdk_session_id = message_item.data.get("session_id", sdk_session_id)
                    else:
                        diagnostic = self._system_diagnostic(message_item)
                        if diagnostic:
                            system_diagnostics.append(diagnostic)
                elif isinstance(message_item, AssistantMessage):
                    for block in message_item.content:
                        if isinstance(block, TextBlock):
                            assistant_text.append(block.text)
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
                metadata={"workflow": workflow},
            )
            raise AgentRunError(detail or exc.__class__.__name__) from exc

        if sdk_session_id and sdk_session_id != session.sdk_session_id:
            session = self.session_manager.set_sdk_session_id(session_id, sdk_session_id)
        else:
            session = self.session_manager.get_session(session_id)

        reply = (raw_result or "\n".join(assistant_text)).strip()
        if result_error:
            if result_errors:
                reply = f"{reply}\n\nErrors:\n- " + "\n- ".join(result_errors)
            if not reply:
                reply = "The agent run failed before a final answer was produced."

        self.session_manager.append_message(
            session_id=session_id,
            role="assistant",
            content=reply,
            workflow=workflow,
            metadata={
                "raw_result": raw_result,
                "skills": skills or self._default_skills(),
            },
        )

        runtime_state = self.session_manager.get_runtime_state()
        return ChatResponse(
            session=runtime_state.session,
            reply=reply,
            workflow=workflow,
            artifacts=runtime_state.artifacts,
            uploads=runtime_state.uploads,
            outputs=runtime_state.outputs,
            activity=runtime_state.activity,
            sdk_session_id=sdk_session_id,
            raw_result=raw_result,
        )

    def _default_skills(self) -> list[str]:
        return [
            "transformation-discovery",
            "dependency-mapping",
            "delivery-planning",
            "transformation-delivery-helper:authority-check",
        ]

    def _runtime_env(self) -> dict[str, str]:
        claude_config_dir = self._claude_config_dir()
        claude_config_dir.mkdir(parents=True, exist_ok=True)
        return {
            "ENABLE_TOOL_SEARCH": "auto:5",
            "CLAUDE_CONFIG_DIR": str(claude_config_dir),
        }

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

    def _validate_runtime_configuration(self) -> None:
        if not self.settings.resolved_claude_cli_path:
            self.session_manager.record_activity(
                event="runtime-error",
                title="Claude Code CLI missing",
                detail="Install the `claude` CLI or set DATA_TRANSFORM_AGENT_CLAUDE_CLI_PATH in .env to the correct binary path.",
                level="error",
            )
            raise AgentRunError(
                "Claude Code CLI was not found. Install the `claude` CLI or set "
                "`DATA_TRANSFORM_AGENT_CLAUDE_CLI_PATH` in `.env` to the correct binary path.",
                status_code=503,
            )
        if not self.settings.anthropic_api_key_configured:
            self.session_manager.record_activity(
                event="runtime-warning",
                title="ANTHROPIC_API_KEY not set",
                detail="If Claude Code is not already authenticated locally, add ANTHROPIC_API_KEY to .env before chatting.",
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
            "requirements-analyst": AgentDefinition(
                description="Use for clarifying transformation scope, missing inputs, source and target characteristics, and essential assumptions.",
                prompt=(
                    "Focus on understanding the transformation request. Pull out source and target facts, key ambiguities, "
                    "and what the user still needs to confirm. Improve the transformation-understanding artifact."
                ),
                tools=[
                    "Read",
                    "Glob",
                    "Grep",
                    "Skill",
                    *mcp_tools,
                ],
                skills=["transformation-discovery"],
                mcpServers=mcp_servers,
                permissionMode="acceptEdits",
            ),
            "dependency-mapper": AgentDefinition(
                description="Use for lineage, dependencies, sequencing, joins, validation points, and data movement dependencies.",
                prompt=(
                    "Focus on upstream and downstream dependencies, required joins, sequencing, lineage, validation, and operational risk. "
                    "Improve the data-dependency-map artifact."
                ),
                tools=[
                    "Read",
                    "Glob",
                    "Grep",
                    "Skill",
                    *mcp_tools,
                ],
                skills=["dependency-mapping"],
                mcpServers=mcp_servers,
                permissionMode="acceptEdits",
            ),
            "implementation-planner": AgentDefinition(
                description="Use for delivery planning, authority checkpoints, packaging, implementation steps, and Python-first output design.",
                prompt=(
                    "Focus on implementation readiness. Produce a practical delivery and authority plan, and shape Python-first implementation outputs "
                    "while keeping room for other target artifacts later."
                ),
                tools=[
                    "Read",
                    "Glob",
                    "Grep",
                    "Skill",
                    *mcp_tools,
                ],
                skills=["delivery-planning"],
                mcpServers=mcp_servers,
                permissionMode="acceptEdits",
            ),
        }
