# HMRC Data Transformation Agent — Project Context

## Purpose

Production-ready AgentCore agent. Runtime is standardized. Only skills and domain data should vary.

## Non-Negotiable Runtime Rules

- Runtime code in `agent/` and `tools/` must not be modified per project.
- Domain behavior lives in `.claude/skills/` and `data/metadata/`.
- External tool calls should be read-only except for request-scoped file storage handled by the runtime contract.

## Tool Selection

Tools are opt-in via the `AGENT_TOOLS` environment variable. Add only the tools this agent needs:

- `athena` — SQL queries against Amazon Athena
- `knowledge_base` — Semantic retrieval from Bedrock Knowledge Base
- `s3` — Read configured S3 sources and store request-scoped files through the runtime storage contract
- `(empty)` — File-system tools only (Read, Write, Bash, Skill)

## Workflow Contract

1. Load the matching skill(s) for the user's request.
2. Read any referenced metadata or sample data files.
3. Use the appropriate tool(s) to retrieve or query data.
4. Save all generated artifacts through the runtime storage contract.
5. Return a clear, concise answer with file references.

## File Contract

- Read sources from: `s3://<S3_READ_BUCKET>/<S3_READ_PREFIX>`
- Primary write target: `s3://<S3_WRITE_BUCKET>/<S3_WRITE_PREFIX>results/<request_id>/{request,deliverables}`
- Local fallback when S3 write is unavailable: `results/<request_id>/{request,deliverables}`
