# HMRC Data Transformation Agent

Production-ready Claude Agent SDK + Amazon Bedrock AgentCore project template.

## What Changes Per Project

- Skills under `.claude/skills/` — agent-specific instructions and task behavior
- Metadata under `data/metadata/` — schemas, source-layout notes, and reference material
- Test fixtures under `data/test-data/` — sample inputs and reference material for simulation and validation

All runtime code (`agent/`, `tools/`, `main.py`) is standardized and should not be modified.

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

`agent/agent_app.py` owns the request-storage contract.

Local request storage is:

```text
results/<request_id>/
├── request/
└── deliverables/
```

## Adding a New Skill

1. Create `.claude/skills/<domain>/SKILL.md`
2. Add any referenced metadata files under `data/metadata/`
3. Keep storage rules aligned with `agent/agent_app.py` and `CLAUDE.md`

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
