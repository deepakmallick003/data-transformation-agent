# HMRC Data Transformation Agent - Architecture

## Runtime Flow

```text
┌──────────────────────────────────────────────────────────────────────┐
│                        INVOCATION SURFACE                            │
│ • Local invoke script                                                │
│ • AgentCore deployed runtime                                         │
│ • User request payload                                               │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     AGENTCORE RUNTIME ENTRYPOINT                     │
│ • main.py                                                            │
│ • agent/agent_app.py                                                 │
│ • generates request_id                                               │
│ • resolves enabled tools from env                                    │
│ • loads CLAUDE.md and starts the Claude runtime                      │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      POLICY AND REQUEST CONTEXT                      │
│ • CLAUDE.md                                                          │
│   - stable runtime policy                                            │
│   - file contract                                                    │
│ • request-specific prompt context                                    │
│   - request_id                                                       │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                            SKILLS LAYER                              │
│ • .claude/skills/...                                                 │
│ • request understanding                                              │
│ • document resolution                                                │
│ • transformation generation                                          │
│ • skill-level control of filenames under request/ and deliverables/  │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                             TOOLS LAYER                              │
│ • tools/s3_tools.py                                                  │
│   - read source objects                                              │
│   - write request-scoped files                                       │
│   - fall back to local results/ when S3 write is unavailable         │
│ • tools/athena_tools.py                                              │
│   - read-only Athena queries                                         │
│   - temporary local scratch for downloaded results                   │
│ • tools/knowledge_base_tools.py                                      │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       EXTERNAL DATA AND OUTPUTS                      │
│ • Read sources from the configured S3 read location                  │
│ • Write request-scoped files under request/ and deliverables/        │
│ • Fall back to local results when S3 write is unavailable            │
│ • Exact storage layouts live in data/metadata/s3_structure.md        │
└──────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────┐
│                      DEPLOYMENT AND ACCESS CONTROL                   │
│ • .env / .env.example                                                │
│   - AGENT_TOOLS                                                      │
│   - S3_READ_*                                                        │
│   - S3_WRITE_*                                                       │
│ • scripts/deploy_agentcore.py                                        │
│ • config/templates/agentcore/agentcore-execution-permissions.template.json │
│   - IAM-scoped read bucket/prefix                                    │
│   - IAM-scoped write bucket/prefix when configured                   │
└──────────────────────────────────────────────────────────────────────┘
```
