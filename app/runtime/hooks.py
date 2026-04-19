from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import HookMatcher
from claude_agent_sdk.types import HookContext, HookEvent, HookInput, HookJSONOutput, SyncHookJSONOutput


def _append_audit_line(audit_path: Path, payload: dict[str, Any]) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _empty_hook_output() -> SyncHookJSONOutput:
    return {}


def build_runtime_hooks(session_root: Path, audit_path: Path) -> dict[HookEvent, list[HookMatcher]]:
    session_root_resolved = session_root.resolve()

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

        if candidate.is_relative_to(session_root_resolved):
            record_activity(
                event="hook-approval",
                title=f"{input_data['tool_name']} allowed",
                detail=f"Approved write within the active runtime workspace: {candidate}",
                level="success",
                metadata={"tool_name": input_data["tool_name"]},
            )
            return _empty_hook_output()

        deny_output: SyncHookJSONOutput = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Write and Edit are limited to the active session workspace. Use the session MCP tools for artifacts and generated outputs.",
            }
        }
        record_activity(
            event="hook-deny",
            title=f"{input_data['tool_name']} denied",
            detail="Write and Edit are limited to the active runtime workspace. Use the session MCP tools for artifacts and generated outputs.",
            level="warning",
            metadata={"tool_name": input_data["tool_name"], "file_path": str(candidate)},
        )
        return deny_output

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
            },
        )
        return _empty_hook_output()

    hooks: dict[HookEvent, list[HookMatcher]] = {
        "PreToolUse": [HookMatcher(matcher="Write|Edit", hooks=[guard_writes])],
        "PostToolUse": [HookMatcher(hooks=[audit_tool_use])],
        "PostToolUseFailure": [HookMatcher(hooks=[audit_tool_failure])],
        "SubagentStop": [HookMatcher(hooks=[audit_subagent_completion])],
    }
    return hooks
