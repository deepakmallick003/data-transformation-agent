# Data Transformation Agent

Data Transformation Agent is a reusable transformation capability platform built around Claude Code, governed session artifacts, MCP surfaces, and a chat-first operator experience.

It is designed to do two things at the same time:

- work as a practical browser-based transformation agent for analysts and engineers
- expose the same transformation capabilities through structured APIs and MCP tools so other agentic systems can reuse them

## What This Project Does

The platform helps a user or another agent move from uploaded transformation evidence to usable outputs such as:

- source and target understanding
- mapping and business rules
- dependency and lineage notes
- implementation-ready Python outputs
- validation and reconciliation plans
- delivery and approval evidence

The system is evidence-aware. It is expected to separate what is verified from uploaded files, what is inferred, and what is still missing.

## Main Building Blocks

### 1. Transformation capability layer

`app/transformation/`

This is the reusable domain layer. It defines the core capability model and execution planning used by every surface:

- `source_analysis`
- `target_contract_analysis`
- `mapping_and_rules`
- `dependency_and_lineage`
- `implementation_generation`
- `validation_and_reconciliation`
- `delivery_readiness`
- `approval_and_evidence`

This layer should hold transformation intent and governance rules, not UI-specific wording or template-driven behavior.

### 2. Runtime orchestration

`app/runtime/`

This layer wraps Claude Code and the runtime plumbing:

- provider selection
- turn prompt construction
- hooks
- internal MCP wiring
- permission handling
- subagents
- status streaming

It decides how Claude executes a transformation plan, but it should not own the transformation domain model itself.

### 3. Session and governed storage

`app/session/`

Each active session is persisted under:

`storage/sessions/<session_id>/`

That session contains:

- `uploads/` for user evidence
- `artifacts/` for governed working documents
- `outputs/` for downloadable deliverables
- `workspace/scratch/` for limited direct scratch edits
- `session.json` for session metadata
- `messages.jsonl` for the conversation record

The agent continuously updates governed artifacts and then derives user-facing outputs from them.

### 4. Product surfaces

The same capability layer is exposed through three main surfaces:

- chat UI
- structured REST APIs
- MCP tools for other agents

The goal is to avoid duplicating transformation logic across these entry points.

## End-To-End Flow

1. A user signs in to the UI with the static credentials from `.env`.
2. The user uploads evidence and sends a natural language transformation request.
3. The runtime builds a transformation plan from the requested workflow and capabilities.
4. Claude executes the plan using controlled tools, hooks, MCP servers, and skills.
5. The session artifacts in `artifacts/` are filled incrementally.
6. The platform derives final outputs into `outputs/`.
7. The UI shows streamed status, chat output, inline files, and downloadable deliverables.

## UI Surface

The browser app is intentionally chat-first:

- fixed left sidebar for session actions and sample test cases
- central conversation thread as the main working surface
- fixed composer for prompts, uploads, and links
- inline progress updates while the agent is working
- inline downloadable outputs when deliverables are generated

The main UI is not meant to expose raw runtime plumbing by default. Internal skills, MCP details, and subagents stay hidden unless explicitly enabled by configuration.

## Login

The agent is protected by a simple static login.

Set these values in `.env`:

```env
AUTH_USERNAME=admin
AUTH_PASSWORD=change-me
```

`AUTH_SECRET` is optional. If you do not set it, the app derives an internal secret automatically from local configuration. Set it explicitly only if you want stable custom cookie signing across environments.

Without a valid login cookie, the UI redirects to `/login` and the API returns `401`.

## Runtime APIs

Main runtime routes:

- `GET /health`
- `GET /api/runtime/capabilities`
- `GET /api/runtime/state`
- `POST /api/runtime/reset`
- `POST /api/runtime/upload`
- `POST /api/runtime/chat`
- `POST /api/runtime/chat/stream`
- `GET /api/runtime/files/{kind}/{name}`
- `GET /api/runtime/test-cases`
- `GET /api/runtime/test-cases/{case}`

The streamed chat route is the live agent surface used by the browser UI.

## Structured Transformation APIs

Structured domain routes:

- `GET /api/transformation/capabilities`
- `POST /api/transformation/execute`
- `POST /api/transformation/source-analysis`
- `POST /api/transformation/target-contract-analysis`
- `POST /api/transformation/mapping-rules`
- `POST /api/transformation/implementation`
- `POST /api/transformation/validation-plan`
- `POST /api/transformation/delivery-pack`
- `POST /api/transformation/approval-requirements`

These all flow through the same underlying transformation service layer used by chat.

## MCP Surfaces

### Internal runtime MCP

Internal MCP servers exist to keep runtime operations governed and auditable:

- `session_context`
- `session_artifacts`
- optional `local_insights`
- optional external runtime integrations such as GitHub or a remote MCP server

These are plumbing surfaces, not the main product capability surface.

### External domain MCP

The reusable domain MCP surface lives in:

`scripts/mcp/transformation_domain_server.py`

It exposes meaningful transformation operations for other agents, such as:

- `analyse_source`
- `interpret_target_contract`
- `generate_mapping_rules`
- `generate_transform_code`
- `generate_validation_plan`
- `prepare_delivery_pack`
- `assess_approval_requirements`

## Hooks And Governance

Hooks are used to make the agent safer and more disciplined, not just to log startup messages.

The current governance direction includes:

- restricting direct edits to approved scratch locations
- requiring governed artifact updates through MCP tools
- gating output generation until key artifact context exists
- auditing important tool and mutation events
- preserving evidence-aware behavior across the run

This keeps the platform closer to a governed transformation system than a free-form SDK demo.

## Permissions

Important runtime controls:

- `RUNTIME_PERMISSION_MODE`
- `ENABLE_DIRECT_FILE_TOOLS`

Direct `Write` and `Edit` access can be enabled, but governed session work should prefer MCP writes for:

- artifacts
- outputs
- auditable mutations

## Provider Modes

Claude provider mode is configuration-driven:

- `auto`
- `anthropic`
- `bedrock`
- `mantle`
- `vertex`
- `foundry`

Useful related environment variables include:

- `CLAUDE_PROVIDER_MODE`
- `CLAUDE_MODEL`
- `AWS_REGION`
- `BEDROCK_BASE_URL`
- `VERTEX_PROJECT_ID`
- `CLOUD_ML_REGION`
- `FOUNDRY_RESOURCE`
- `FOUNDRY_BASE_URL`

Direct Anthropic API key usage still works through `ANTHROPIC_API_KEY`.

## Outputs And Deliverables

The session `outputs/` folder is the user-facing deliverable area.

Typical outputs include:

- `transformation_summary.md`
- `transformation_readme.md`
- `mapping_rules.md`
- `validation_summary.md`
- a generated Python transformation script
- optional sample output files

`transformation_summary.md` is the merged summary built from the governed session artifacts.

`transformation_readme.md` explains the outputs and how to use them.

## Sample Test Cases

Built-in preload buttons read from:

`test/sampletestdata/`

When a user clicks a test case:

1. `chat_request.txt` is loaded into the composer
2. the remaining files in that case folder are staged as attachments
3. nothing is auto-submitted

This keeps test cases fast to review and rerun without hiding what will actually be sent.

## Project Layout

```text
app/
├── api/
├── core/
├── runtime/
│   ├── mcp/
│   ├── hooks.py
│   ├── prompts.py
│   └── providers.py
├── session/
├── transformation/
└── web/
claude-plugins/
scripts/
└── mcp/
templates/
storage/
test/
```

## Running Locally

1. Create and activate a virtual environment.
2. Install dependencies.
3. Configure `.env` with login credentials, Claude provider settings, and any MCP-related options.
4. Start the API.
5. Start the UI.
6. Open the UI in a browser and sign in.

Typical entry points in this repo:

- `run_api.py`
- `run_ui.py`

## Render Or Other Hosted Deployments

This project currently depends on the Claude CLI at runtime. That means a hosted deployment must have the CLI installed and available to the running process.

For `CLAUDE_CLI_PATH`:

- use `claude` if the CLI is installed on the container image `PATH`
- use an absolute path only if your deployment image installs it somewhere non-standard
- do not set it to a local machine path like `/Users/.../claude` on Render, because that path will not exist there

If the Claude CLI is not installed in the deployed environment, the chat runtime will not work.

A practical Render setup is usually:

1. one API web service
2. one UI web service
3. shared auth and provider env vars across both
4. `BACKEND_URL` on the UI service pointing to the public API URL

Typical API service env values:

```env
API_HOST=0.0.0.0
AUTH_USERNAME=admin
AUTH_PASSWORD=your-password
CLAUDE_CLI_PATH=claude
CLAUDE_PROVIDER_MODE=anthropic
ANTHROPIC_API_KEY=your-key
```

Notes:

- `API_PORT` can usually be omitted on Render because the app now also respects Render's injected `PORT`
- if you use Bedrock, Vertex, Mantle, or Foundry, set the corresponding provider env vars instead of `ANTHROPIC_API_KEY`
- `LOCAL_INSIGHTS_MCP_ENABLED=false` may be a sensible hosted default if you want a smaller runtime surface

Typical UI service env values:

```env
UI_HOST=0.0.0.0
AUTH_USERNAME=admin
AUTH_PASSWORD=your-password
BACKEND_URL=https://your-api-service.onrender.com
```

If you want a single-service deployment instead, the current project would need a small serving/proxy adjustment because the UI and API are started separately today.

## Extending The Platform

If you want to add a new feature, use these boundaries:

- add a new reusable transformation capability under `app/transformation`
- add runtime prompt or execution behavior under `app/runtime`
- add governed session or artifact behavior under `app/session`
- add new REST exposure in `app/api`
- add new external domain MCP tools in `scripts/mcp/transformation_domain_server.py`
- add or refine hooks where mutation control or auditability matters
- add UI-only behavior in `app/web`

Try not to put domain logic directly into the UI or duplicate capability logic across API, chat, and MCP surfaces.

## More Detail

Architecture and extension guidance lives in [docs/architecture.md](docs/architecture.md).
