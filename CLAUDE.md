# Data Transformation Project Memory

This repository hosts a Python-first document and data transformation agent for local and internal testing.

When the agent works inside this project:

- Treat `storage/sessions/<session-id>/` as the active working area for user-specific outputs.
- Keep the session artifacts current using the `session_artifacts` MCP tools before finalising a response.
- Use `session_context` MCP tools to inspect uploads, notes, and session templates, and `local_insights` for runtime or repo diagnostics when needed.
- Prefer concise clarification when source, target, security, or delivery constraints are missing.
- Prefer Python implementation output in v1 unless the user explicitly asks for another target format.
- Use project Skills from `.claude/skills/` when the task matches discovery, dependency mapping, or delivery planning.
- Use the local plugin to strengthen delivery and authority-pack style output when sign-off or implementation readiness is involved.
