from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import HookMatcher
from claude_agent_sdk.types import HookContext, HookEvent, HookInput, HookJSONOutput, SyncHookJSONOutput

from app.transformation.governance import TransformationGovernancePolicy
from app.transformation.models import CapabilityId


def _append_audit_line(audit_path: Path, payload: dict[str, Any]) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _empty_hook_output() -> SyncHookJSONOutput:
    return {}


def build_runtime_hooks(
    *,
    governance: TransformationGovernancePolicy,
    session_root: Path,
    audit_path: Path,
    selected_capabilities: list[CapabilityId],
) -> dict[HookEvent, list[HookMatcher]]:
    session_root_resolved = session_root.resolve()
    allowed_roots = [path.resolve() for path in governance.allowed_direct_write_roots()]
    protected_roots = [path.resolve() for path in governance.protected_session_roots()]

    def record_activity(
        *,
        event: str,
        title: str,
        detail: str | None = None,
        level: str = "info",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        _append_audit_line(
            audit_path,
            {
                "created_at": datetime.now(UTC).isoformat(),
                "event": event,
                "title": title,
                "detail": detail,
                "level": level,
                "metadata": metadata or {},
            },
        )

    async def guard_writes(
        input_data: HookInput,
        tool_use_id: str | None,
        _context: HookContext,
    ) -> HookJSONOutput:
        del tool_use_id
        if input_data["hook_event_name"] != "PreToolUse":
            return _empty_hook_output()
        if input_data["tool_name"] not in {"Write", "Edit"}:
            return _empty_hook_output()

        file_path = input_data["tool_input"].get("file_path")
        if not isinstance(file_path, str) or not file_path:
            return _empty_hook_output()

        candidate = Path(file_path)
        if not candidate.is_absolute():
            candidate = Path(input_data["cwd"]) / candidate
        candidate = candidate.resolve()

        if any(candidate.is_relative_to(root) for root in allowed_roots):
            record_activity(
                event="hook-approval",
                title=f"{input_data['tool_name']} allowed",
                detail=f"Approved direct write inside the scratch workspace: {candidate}",
                level="success",
                metadata={
                    "tool_name": input_data["tool_name"],
                    "capabilities": selected_capabilities,
                },
            )
            return _empty_hook_output()

        if any(candidate.is_relative_to(root) for root in protected_roots):
            reason = (
                "Direct edits to session artifacts, uploads, and outputs are denied. "
                "Use the session_artifacts MCP tools so the change is governed and auditable."
            )
        elif candidate.is_relative_to(session_root_resolved):
            reason = (
                "Direct edits inside the active session are limited to workspace/scratch. "
                "Use session_artifacts MCP tools for artifacts and outputs."
            )
        else:
            reason = (
                "Direct edits outside the approved session scratch area are denied for this transformation runtime."
            )

        record_activity(
            event="hook-deny",
            title=f"{input_data['tool_name']} denied",
            detail=reason,
            level="warning",
            metadata={
                "tool_name": input_data["tool_name"],
                "file_path": str(candidate),
                "capabilities": selected_capabilities,
            },
        )
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }

    async def govern_session_mutations(
        input_data: HookInput,
        tool_use_id: str | None,
        _context: HookContext,
    ) -> HookJSONOutput:
        del tool_use_id
        if input_data["hook_event_name"] != "PreToolUse":
            return _empty_hook_output()

        tool_name = input_data["tool_name"]
        tool_input = input_data.get("tool_input", {})

        if tool_name == "mcp__session_artifacts__write_session_artifact":
            artifact_name = str(tool_input.get("artifact_name", "artifact"))
            reason = governance.artifact_update_gate_reason(
                artifact_name=artifact_name,
                reason=tool_input.get("reason"),
            )
            if reason is None:
                return _empty_hook_output()
        elif tool_name == "mcp__session_artifacts__write_session_output":
            reason = governance.output_write_gate_reason()
            if reason is None:
                return _empty_hook_output()
        else:
            return _empty_hook_output()

        record_activity(
            event="governance-deny",
            title=f"Governance blocked {tool_name}",
            detail=reason,
            level="warning",
            metadata={
                "tool_name": tool_name,
                "capabilities": selected_capabilities,
            },
        )
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }

    async def audit_tool_use(
        input_data: HookInput,
        tool_use_id: str | None,
        _context: HookContext,
    ) -> HookJSONOutput:
        if input_data["hook_event_name"] != "PostToolUse":
            return _empty_hook_output()
        record_activity(
            event="tool-complete",
            title=f"Tool finished: {input_data['tool_name']}",
            detail=f"Completed tool call in session {input_data['session_id']}.",
            level="info",
            metadata={
                "tool_name": input_data["tool_name"],
                "tool_use_id": tool_use_id,
                "session_id": input_data["session_id"],
                "capabilities": selected_capabilities,
            },
        )
        return _empty_hook_output()

    async def audit_tool_failure(
        input_data: HookInput,
        tool_use_id: str | None,
        _context: HookContext,
    ) -> HookJSONOutput:
        if input_data["hook_event_name"] != "PostToolUseFailure":
            return _empty_hook_output()
        record_activity(
            event="tool-failed",
            title=f"Tool failed: {input_data['tool_name']}",
            detail=f"Tool call failed in session {input_data['session_id']}.",
            level="error",
            metadata={
                "tool_name": input_data["tool_name"],
                "tool_use_id": tool_use_id,
                "session_id": input_data["session_id"],
                "capabilities": selected_capabilities,
            },
        )
        return _empty_hook_output()

    async def audit_subagent_completion(
        input_data: HookInput,
        tool_use_id: str | None,
        _context: HookContext,
    ) -> HookJSONOutput:
        if input_data["hook_event_name"] != "SubagentStop":
            return _empty_hook_output()
        record_activity(
            event="subagent-stop",
            title=f"Subagent completed: {input_data['agent_type']}",
            detail=f"Subagent finished work in session {input_data['session_id']}.",
            level="success",
            metadata={
                "agent_type": input_data["agent_type"],
                "tool_use_id": tool_use_id,
                "session_id": input_data["session_id"],
                "capabilities": selected_capabilities,
            },
        )
        return _empty_hook_output()

    async def audit_prompt_submit(
        input_data: HookInput,
        tool_use_id: str | None,
        _context: HookContext,
    ) -> HookJSONOutput:
        del tool_use_id
        if input_data["hook_event_name"] != "UserPromptSubmit":
            return _empty_hook_output()
        readiness = governance.assess_readiness()
        record_activity(
            event="prompt-submit",
            title="Transformation prompt submitted",
            detail=(
                "Capabilities requested: "
                + ", ".join(selected_capabilities)
                + f" | source_clear={readiness.source_clear} target_clear={readiness.target_clear}"
            ),
            level="info",
            metadata={"capabilities": selected_capabilities},
        )
        return _empty_hook_output()

    return {
        "PreToolUse": [
            HookMatcher(matcher="Write|Edit", hooks=[guard_writes]),
            HookMatcher(hooks=[govern_session_mutations]),
        ],
        "PostToolUse": [HookMatcher(hooks=[audit_tool_use])],
        "PostToolUseFailure": [HookMatcher(hooks=[audit_tool_failure])],
        "UserPromptSubmit": [HookMatcher(hooks=[audit_prompt_submit])],
        "SubagentStop": [HookMatcher(hooks=[audit_subagent_completion])],
    }
