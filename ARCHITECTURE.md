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
│ • resolves S3 read roots and write fallback targets for this request │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      POLICY AND REQUEST CONTEXT                      │
│ • CLAUDE.md                                                          │
│   - stable runtime policy                                            │
│   - file contract                                                    │
│ • config/templates/prompts/agent_prompt.md                           │
│ • request-specific prompt context                                    │
│   - request_id                                                       │
│   - resolved read root                                               │
│   - resolved write root                                              │
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
│ • Read sources                                                       │
│   - s3://<S3_READ_BUCKET>/<S3_READ_PREFIX>                           │
│ • Request-scoped writes                                              │
│   - s3://<S3_WRITE_BUCKET>/agents/<agent_name>/results/<request_id>/ │
│     - request/                                                       │
│     - deliverables/                                                  │
│ • Local fallback                                                     │
│   - results/<request_id>/                                            │
│     - request/                                                       │
│     - deliverables/                                                  │
└──────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────┐
│                      DEPLOYMENT AND ACCESS CONTROL                   │
│ • .env / .env.example                                                │
│   - AGENT_TOOLS                                                      │
│   - S3_READ_*                                                        │
│   - S3_WRITE_*                                                       │
│ • config/settings.py                                                 │
│ • config/deployment.py                                               │
│ • scripts/deploy_agentcore.py                                        │
│ • config/templates/agentcore/agentcore-execution-permissions.template.json │
│   - IAM-scoped read bucket/prefix                                    │
│   - IAM-scoped write bucket/prefix when configured                   │
└──────────────────────────────────────────────────────────────────────┘
```
