# HMRC Data Transformation Agent - Project Context

## Purpose

Production-ready AgentCore project context.
This file defines project-wide operating rules that apply to any agent in this repository.
Agent-specific behavior should vary through skills and metadata, not through ad hoc storage conventions.

## Non-Negotiable Runtime Rules

- Runtime code in `agent/` and `tools/` must not be modified per project.
- Domain behavior lives in `.claude/skills/` and `data/metadata/`.
- All external tool calls must be read-only unless explicitly noted in a skill.
- These rules apply equally to transformation agents, code-generation agents, interview agents, and future agent types in this project.

## Instruction Authority Order

When instructions overlap or conflict, agents must apply them in this order:

1. `CLAUDE.md` - global operating rules, storage rules, and cross-agent behavior
2. `data/metadata/*` - source-specific structure, retrieval order, provenance, and staging rules
3. `.claude/skills/*` - task guidance, domain interpretation, and which metadata to consult
4. Request-specific reasoning - only within the constraints above

Skills must not redefine storage semantics, retention expectations, or file-placement rules.
If a skill conflicts with `CLAUDE.md`, `CLAUDE.md` wins.
If a skill conflicts with source metadata, the metadata file wins.

## Tool Selection

Tools are opt-in via the `AGENT_TOOLS` environment variable.  
Add only the tools the current agent needs:

- `athena` — SQL queries against Amazon Athena
- `knowledge_base` — Semantic retrieval from Bedrock Knowledge Base
- `s3` — Read-only access to an S3 bucket
- *(empty)* — File-system tools only (Read, Write, Bash, Skill)

## Workflow Contract

1. Load the matching skill(s) for the user's request
2. Read any referenced metadata or sample data files
3. Apply storage and retrieval rules from this file and any relevant metadata file
4. Use the appropriate tool(s) to retrieve or query data
5. Save all generated artifacts under the request-scoped folder
6. Return a clear, concise answer with file references

Skills may guide the agent toward relevant local files, S3 prefixes, tables, knowledge sources, or other external repositories.
Skills may explain how to use a source.
Skills must not dictate where retrieved material is stored or invent alternate folder strategies.

## File Contract

All agent activity must be scoped to a single `request_id`.
All files created or used during a request MUST live under the request folder.

📁 `data/agents/<agent-name>/requests/<request_id>/`

The following subfolders have strict, non-overlapping purposes.

### request/

**Purpose:** Immutable record of what the agent was asked to do.

- Written once at the start of the request
- Never modified after creation
- Contains user intent and resolved context only
- Does not contain fetched evidence or intermediate reasoning outputs

Examples:

- user_query.json
- context.json
- input-brief.md
- source-selection.json

---

### evidence/

**Purpose:** Verbatim copies of all data retrieved from external systems.

- Written immediately when data is fetched
- Must preserve original filenames and structure where possible
- Must not be altered or summarised
- Must preserve provenance sufficient to trace source location and selected version
- Represents authoritative external input staged for this request

Examples:

- athena/query-results.csv
- api/response.json
- s3/source-file.md
- repository/specification.md

---

### work/

**Purpose:** Machine-readable artifacts derived by the agent for reasoning or downstream automation.

- Created during agent reasoning
- Internal to the agent or other automated processes
- Optional — write only if reuse or inspection is required
- May contain drafts, parsed structures, plans, and intermediate outputs
- In multi-agent flows, agents should either coordinate on shared files carefully or use agent-specific subfolders to avoid overwrite conflicts

Examples:

- parsed_source.json
- normalized_schema.yaml
- analysis_plan.json
- interview_outline.json
- code_structure.json

---

### deliverables/

**Purpose:** Final, authoritative outputs intended for users or downstream consumers.

- Written only after reasoning is complete
- Represents the final outcome of the request
- Must not be used as working memory during reasoning
- Drafts belong in `work/` until they are final

Examples:

- response.md
- summary.json
- final-report.pdf
- generated-code.zip
- interview-pack.md

---

### Storage Rules (Non-Negotiable)

- The same content must NOT be duplicated across folders
- Agents may read from `request/` and `evidence/` freely
- Agents should prefer reading from `work/` if present
- Agents must NOT read from `deliverables/` during reasoning
- `request/`, `evidence/`, `work/`, and `deliverables/` are execution-time storage semantics and must be used consistently across all agents
- Source metadata files define where data lives externally; they do not replace the request folder contract
- Persistent shared context outside a request folder is a future concern and must not be improvised inside skills
- Skills should change agent behavior, but not the storage contract defined here
