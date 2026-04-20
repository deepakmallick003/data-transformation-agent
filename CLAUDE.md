# Data Transformation Project Memory

This repository hosts a Python-first document and data transformation agent for local and internal testing.

When the agent works inside this project:

- Treat the transformation capability layer in `app/transformation/` as the reusable product surface.
- Treat the runtime session as governed working state rather than the definition of the product.
- Keep session artifacts current using the `session_artifacts` MCP tools before finalising a response.
- Use `session_context` MCP tools to inspect uploads, notes, and artifact blueprints, and `local_insights` for runtime or repo diagnostics when needed.
- Prefer direct writes only inside `workspace/scratch`; use MCP tools for artifacts and outputs.
- Prefer concise clarification when source, target, security, or delivery constraints are missing.
- Prefer Python implementation output in v1 unless the user explicitly asks for another target format.
- Prefer capability-oriented skills from `.claude/skills/` such as `source-analysis`, `target-contract-analysis`, `mapping-and-rules`, `dependency-and-lineage`, `implementation-generation`, `validation-and-reconciliation`, and `delivery-readiness`.
- Use the local plugin capability `approval-and-evidence` when sign-off, evidence packs, or governance readiness matter.
