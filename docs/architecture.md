# Architecture Guide

## 1. Core Boundary

This project now treats reusable transformation capability as the center of the system.

### `app/transformation`

Owns:

- capability catalog
- structured execution planning
- governance policy
- capability-oriented request and response models

Current files:

- `app/transformation/capabilities.py`
- `app/transformation/models.py`
- `app/transformation/service.py`
- `app/transformation/governance.py`

This layer should describe what the transformation platform can do, not how Claude, FastAPI, or the UI currently happens to invoke it.

### `app/runtime`

Owns Claude runtime plumbing:

- Claude Agent SDK options
- provider initialization
- runtime prompts
- hook wiring
- internal MCP registration
- subagent definitions
- streamed chat execution and friendly progress events

Current files:

- `app/runtime/agent.py`
- `app/runtime/providers.py`
- `app/runtime/prompts.py`
- `app/runtime/hooks.py`
- `app/runtime/mcp/*`

### `app/session`

Owns runtime state and governed working storage:

- uploads
- artifacts
- outputs
- user-facing progress status snapshots
- scratch workspace
- runtime activity audit
- artifact template instantiation

Current files:

- `app/session/manager.py`
- `app/session/templates.py`

### `app/api`

Owns HTTP contracts only.

It should:

- validate request shapes
- map requests onto transformation execution plans
- return structured responses

It should not invent transformation logic that bypasses `app/transformation`.

### `app/web`

Owns the existing UI shell and should remain a consumer of API surfaces rather than a hidden source of business logic.

## 2. Capability Model

The current reusable capabilities are:

1. `source_analysis`
2. `target_contract_analysis`
3. `mapping_and_rules`
4. `dependency_and_lineage`
5. `implementation_generation`
6. `validation_and_reconciliation`
7. `delivery_readiness`
8. `approval_and_evidence`

Artifact filenames remain useful session memory, but they are not the capability model.

Artifact mappings currently live in [app/session/templates.py](/Users/deepak/AgenticAI/data-transformation-agent/app/session/templates.py).

## 3. API Surface

### Existing runtime/chat endpoints

- `/login`
- `/api/runtime/chat`
- `/api/runtime/chat/stream`
- `/api/runtime/upload`
- `/api/runtime/reset`
- `/api/runtime/state`
- `/api/runtime/capabilities`
- `/api/runtime/test-cases`
- `/api/runtime/test-cases/{case}`
- `/api/runtime/files/{kind}/{name}`

### Structured transformation endpoints

- `/api/transformation/capabilities`
- `/api/transformation/execute`
- `/api/transformation/source-analysis`
- `/api/transformation/target-contract-analysis`
- `/api/transformation/mapping-rules`
- `/api/transformation/implementation`
- `/api/transformation/validation-plan`
- `/api/transformation/delivery-pack`
- `/api/transformation/approval-requirements`

All structured endpoints should call `TransformationCapabilityService.plan_structured_request(...)` and then execute that plan through `ClaudeTransformationAgent.run_execution_plan(...)`.

The streamed chat route should call `ClaudeTransformationAgent.stream_turn(...)` and keep the existing non-streaming route intact for compatibility.

## 4. MCP Surface

### Internal/runtime MCP

Lives under `app/runtime/mcp`.

Use this for:

- session context
- uploads
- artifact reads and writes
- runtime diagnostics

Do not expose internal helper MCP tools externally unless the tool is meaningful as a reusable product capability.

### External/domain MCP

Lives at [scripts/mcp/transformation_domain_server.py](/Users/deepak/AgenticAI/data-transformation-agent/scripts/mcp/transformation_domain_server.py).

Use this for reusable domain actions other agents care about:

- source analysis
- target contract interpretation
- mapping rule generation
- transformation implementation generation
- validation plan generation
- delivery pack preparation
- approval and evidence assessment

## 5. Hook And Permission Model

Runtime governance currently does the following:

- restricts direct `Write` and `Edit` calls to `workspace/scratch`
- forces governed artifact and output changes through `session_artifacts` MCP tools
- requires a reason when mutating artifacts
- blocks output generation until source and target clarity exist
- records prompt submission, tool completion, failures, and subagent completion

Key files:

- [app/runtime/hooks.py](/Users/deepak/AgenticAI/data-transformation-agent/app/runtime/hooks.py)
- [app/transformation/governance.py](/Users/deepak/AgenticAI/data-transformation-agent/app/transformation/governance.py)

If you need stronger restrictions, prefer adding them to governance policy first and then adapting hooks or runtime tool permissions to enforce them.

## 6. Evidence Discipline

The agent is now expected to:

- split mixed prompts into distinct transformation scenarios
- compare those scenarios with uploaded evidence
- separate verified work from inferred assumptions
- state missing required inputs clearly
- avoid overclaiming certainty
- say which deliverables can be generated now and which remain blocked

The main implementation points for this are:

- [app/runtime/prompts.py](/Users/deepak/AgenticAI/data-transformation-agent/app/runtime/prompts.py)
- [app/transformation/service.py](/Users/deepak/AgenticAI/data-transformation-agent/app/transformation/service.py)
- capability and plugin `SKILL.md` files under `.claude/skills/` and `claude-plugins/`

## 7. UI And Streaming Model

The frontend keeps the existing Flask shell, but the interaction model is now more platform-like:

- a simple `.env`-driven login gate protects the UI and API
- `AUTH_SECRET` can be omitted because the app derives an internal cookie-signing secret automatically for local use
- conversation is the main work surface
- uploads and deliverables appear inline in the chat history
- attachments are staged in the composer and uploaded when the user sends
- raw internal skill names are hidden from the operator UI
- streamed progress is shown as temporary in-chat bullet updates instead of a persistent dashboard panel
- developer/runtime detail is hidden by default and can be exposed through configuration
- partial text and runtime status updates flow through `/api/runtime/chat/stream`
- built-in preload buttons can hydrate the composer from `test/sampletestdata/<case>/chat_request.txt` plus sibling files
- `transformation_summary.md` is derived from the governed session artifacts and exposed as a downloadable output
- `transformation_readme.md` explains how to use the generated outputs

The main files are:

- [app/web/templates/index.html](/Users/deepak/AgenticAI/data-transformation-agent/app/web/templates/index.html)
- [app/web/static/app.js](/Users/deepak/AgenticAI/data-transformation-agent/app/web/static/app.js)
- [app/web/static/styles.css](/Users/deepak/AgenticAI/data-transformation-agent/app/web/static/styles.css)

Useful UI configuration flags live in [app/core/config.py](/Users/deepak/AgenticAI/data-transformation-agent/app/core/config.py):

- `ui_show_developer_panel`
- `ui_show_mode_picker`
- `ui_show_subagents`
- `ui_show_document_panel`
- `ui_show_suggested_prompts`
- `ui_exposed_modes`
- `ui_exposed_subagents`

## 8. Claude Provider Configuration

Provider resolution lives in [app/runtime/providers.py](/Users/deepak/AgenticAI/data-transformation-agent/app/runtime/providers.py).

Supported modes:

- `anthropic`
- `bedrock`
- `mantle`
- `vertex`
- `foundry`

Selection is driven by:

- `CLAUDE_PROVIDER_MODE`
- related provider-specific settings such as `AWS_REGION`, `BEDROCK_BASE_URL`, `VERTEX_PROJECT_ID`, or `FOUNDRY_BASE_URL`
- relevant environment variables already present in the process

The runtime still supports direct Anthropic API key usage.

## 9. Extension Recipes

### Add a new transformation capability

1. Add the capability definition in [app/transformation/capabilities.py](/Users/deepak/AgenticAI/data-transformation-agent/app/transformation/capabilities.py).
2. Decide which workflow it belongs to and update `WORKFLOW_CAPABILITY_MAP`.
3. Map it to governed artifacts in [app/session/templates.py](/Users/deepak/AgenticAI/data-transformation-agent/app/session/templates.py) if needed.
4. Update any governance gates in [app/transformation/governance.py](/Users/deepak/AgenticAI/data-transformation-agent/app/transformation/governance.py).
5. Expose it through API and MCP only if it is meaningful as a reusable surface.

### Add a new skill

1. Create a new `SKILL.md` under `.claude/skills/<skill_name>/`.
2. Use the real Claude skill naming convention used by the repo, including hyphenated names where the runtime expects them.
3. Link the skill from the capability definition in `app/transformation/capabilities.py`.
4. If it belongs in a plugin, place it under `claude-plugins/<plugin>/skills/<skill_name>/`.

### Add a new internal/runtime MCP tool

1. Decide whether it is truly runtime/session plumbing.
2. Add the tool to the relevant file under `app/runtime/mcp/servers/`.
3. Register the server in `app/runtime/mcp/registry.py` if needed.
4. Update hooks or governance if the tool mutates state.

### Add a new external/domain MCP tool

1. Add it to [scripts/mcp/transformation_domain_server.py](/Users/deepak/AgenticAI/data-transformation-agent/scripts/mcp/transformation_domain_server.py).
2. Route it through `TransformationCapabilityService` and `ClaudeTransformationAgent.run_execution_plan(...)`.
3. Keep the tool domain-shaped and avoid exposing low-level helper operations.

### Add a new API endpoint

1. Add the request and response shape if needed in `app/transformation/models.py`.
2. Add the endpoint in [app/api/app.py](/Users/deepak/AgenticAI/data-transformation-agent/app/api/app.py).
3. Reuse `TransformationCapabilityService` planning rather than duplicating prompt logic.
4. Prefer thin HTTP handlers that call shared services.
5. If the endpoint is interactive or long-running, decide whether it should also have a streamed variant.

### Add a new hook or governance rule

1. Put the business rule in [app/transformation/governance.py](/Users/deepak/AgenticAI/data-transformation-agent/app/transformation/governance.py).
2. Enforce or audit it from [app/runtime/hooks.py](/Users/deepak/AgenticAI/data-transformation-agent/app/runtime/hooks.py).
3. If the rule affects direct tool access, update runtime tool permissions in [app/runtime/agent.py](/Users/deepak/AgenticAI/data-transformation-agent/app/runtime/agent.py).
4. Prefer prompts and skills for evidence-discipline behavior first; use hooks for governance and audit boundaries.

### Add a new plugin

1. Create a new directory under `claude-plugins/`.
2. Add `.claude-plugin/plugin.json`.
3. Add plugin-local skills only when the plugin provides a reusable focused augmentation rather than decoration.
4. Register the plugin in runtime initialization if it should load by default.

### Add a new provider mode

1. Extend the mode union in [app/core/config.py](/Users/deepak/AgenticAI/data-transformation-agent/app/core/config.py) and [app/runtime/providers.py](/Users/deepak/AgenticAI/data-transformation-agent/app/runtime/providers.py).
2. Map the provider’s required environment variables in `resolve_claude_provider(...)`.
3. Update runtime capability reporting in [app/api/app.py](/Users/deepak/AgenticAI/data-transformation-agent/app/api/app.py).
4. Document the new mode in `README.md` and this guide.

## 10. Backward Compatibility Notes

Compatibility currently preserved:

- existing UI still works
- `/api/runtime/chat` still works
- `/api/runtime/chat/stream` is additive rather than replacing the old path
- upload/artifact/output/session behavior still works
- legacy skill names still resolve through compatibility wrappers

Intentional changes:

- the UI now centers one primary Transformation Agent
- direct session file edits are more constrained
- capability naming is now internal-first and reusable surface-first
