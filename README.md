# HMRC Data Transformation Agent

Production-ready Claude Agent SDK + Amazon Bedrock AgentCore project template.

## What Changes Per Project

- Skills under `.claude/skills/` — agent-specific instructions and task behavior
- Metadata under `data/metadata/` — schemas, source-layout notes, and reference material

All runtime code (`agent/`, `tools/`, `main.py`) is standardized and should not be modified.

## Architecture

For the high-level architecture diagram, see
[ARCHITECTURE.md](./ARCHITECTURE.md).

## Runtime Control

The main runtime control points are:

- `CLAUDE.md` defines the stable file contract and runtime policy.
- `agent/agent_app.py` creates the request id, loads the project prompt context, and starts the Claude runtime.
- `tools/s3_tools.py` owns the S3 read, write, and local fallback logic.
- `.env` values control tool enablement, S3 bucket/prefix selection, and whether scoped S3 write IAM is rendered.
- `scripts/deploy_agentcore.py` plus `config/templates/agentcore/agentcore-execution-permissions.template.json` control deployment-time IAM scope.

For most projects, customization should happen mainly in:

- `.claude/skills/`
- `data/metadata/`
- `.env` values derived from `.env.example`

## Enabled Tools

Configured via `AGENT_TOOLS` in `.env`. See `.env.example` for available options and required env vars.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # then fill in values
python -m dotenv run -- python main.py
```

`main.py` does not load `.env` by itself. For local development, use `python -m dotenv run -- ...` so the env file is loaded without changing application code.

## Test Locally

Start the local runtime in one terminal:

```bash
source .venv/bin/activate
python -m dotenv run -- python main.py
```

Invoke the local agent from another terminal:

```bash
source .venv/bin/activate
python scripts/invoke_agentcore.py --dev "user query"
```

Replace `"user query"` with the prompt you want to test.

## Request Storage

The runtime uses the request-storage contract defined by `CLAUDE.md` and implemented by `tools/s3_tools.py`.
For the exact S3 and local storage layouts, see [data/metadata/s3_structure.md](./data/metadata/s3_structure.md).

## Storage Policy Matrix

Use this policy when deciding where request-scoped artifacts should go:

| Scenario | Default behavior | Extra persistence allowed? | Notes |
| --- | --- | --- | --- |
| Local development run | Store under `results/<request_id>/` | Yes, if a skill explicitly calls an external write tool | Local `Write` stays in the repo workspace |
| Deployed AgentCore run | Store under `results/<request_id>/` inside the runtime workspace | Yes, if a skill explicitly calls an external write tool | Runtime-local files are not the user's laptop/project folder |
| Skill explicitly requests S3 mirroring | Keep the local request-scoped result layout | Yes, mirror through the S3 write tool | Exact S3 layout is defined in `data/metadata/s3_structure.md` |
| User asks for a custom local/external destination | Do not assume it is possible | Only if a dedicated tool exists for that destination | Prompt text alone cannot make deployed `Write` target the user's machine |

## Adding a New Skill

1. Create `.claude/skills/<domain>/SKILL.md`
2. Add any referenced metadata files under `data/metadata/`
3. Keep storage rules aligned with `CLAUDE.md` and the relevant tool behavior

## Deploy to AgentCore

Use `main.py` as the runtime entrypoint for AgentCore deployments.

This repo includes `scripts/deploy_agentcore.py`, which fills the deployment templates from defaults plus environment variables, then runs the AgentCore CLI.

Before deploying, make sure you have:

- Docker installed and running
- AWS credentials available in your shell
- the project virtualenv activated
- an IAM execution role created for this agent

For the normal flow, you do not need to edit the Dockerfile or AgentCore YAML templates.
The deploy script fills in the Dockerfile, AgentCore YAML, trust policy, and execution-permissions policy from environment variables and uses fixed defaults for the rest.

For IAM, the deploy script uses the AgentCore trust policy and execution-permissions templates in the root config area directly when it creates or updates the execution role.
For deployment artifacts, it uses a fixed bucket name pattern: `bedrock-agentcore-codebuild-sources-<account-id>-<region>`.
If the deployment bucket must be created, the tag variables in `.env` are required. If they are missing, the flow fails with a clear message instead of attempting an untagged bucket create.

Prepare and deploy:

```bash
source .venv/bin/activate
python -m dotenv run -- python scripts/deploy_agentcore.py check
python -m dotenv run -- python scripts/deploy_agentcore.py deploy
```

The deployment helper will:

- create or update the IAM execution role from the trust and permissions templates unless `AGENTCORE_EXECUTION_ROLE_ARN` is explicitly provided
- create the CodeBuild source bucket when needed
- write `Dockerfile` and `.bedrock_agentcore.yaml` in the repo root
- run `agentcore deploy`

If you only want to validate that the deployment templates and environment values resolve cleanly, run:

```bash
python scripts/deploy_agentcore.py prepare
```

That command writes `Dockerfile` and `.bedrock_agentcore.yaml` in the repo root without starting a deployment.

Check deployment status:

```bash
python scripts/deploy_agentcore.py status
```

## Test Deployed Agent

Once the runtime is deployed, invoke it from the terminal:

```bash
source .venv/bin/activate
python scripts/invoke_agentcore.py "user query"
```

If you have more than one deployed runtime configured, specify the runtime name explicitly:

```bash
python scripts/invoke_agentcore.py --agent <agent-name> "user query"
```

You can also invoke the deployed runtime with the deployment helper:

```bash
python scripts/deploy_agentcore.py invoke "user query"
```
