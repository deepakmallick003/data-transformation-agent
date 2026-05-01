# HMRC Data Transformation Agent — Project Context

## Purpose

Production-ready AgentCore agent. Runtime is standardized. Only skills and domain data should vary.

## Non-Negotiable Runtime Rules

- Runtime code in `agent/` and `tools/` must not be modified per project.
- Domain behavior lives in `.claude/skills/` and `data/metadata/`.
- All external tool calls must be read-only unless explicitly noted in a skill.

## Tool Selection

Tools are opt-in via the `AGENT_TOOLS` environment variable. Add only the tools this agent needs:

- `athena` — SQL queries against Amazon Athena
- `knowledge_base` — Semantic retrieval from Bedrock KnowledgeBase
- `s3` — Read-only access to an S3 bucket
- `(empty)` — File-system tools only (Read, Write, Bash, Skill)

## Workflow Contract

1. Load the matching skill(s) for the user's request.
2. Read any referenced metadata or sample data files.
3. Use the appropriate tool(s) to retrieve or query data.
4. Save all generated artifacts under the request-scoped folder.
5. Return a clear, concise answer with file references.

## File Contract

- External tool output: `results/{request_id}/request`
- Processed output: `results/{request_id}/deliverables`
