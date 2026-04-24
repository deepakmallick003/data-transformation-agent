## S3 Storage Model - Shared Source Material & Agent Requests

This bucket is a shared, central store used by multiple agents.
All agents MUST follow the same object layout and semantics.
This file defines S3 layout, retrieval order, provenance expectations, and staging behavior.
It does not define general storage policy outside the S3 context; that is governed by `CLAUDE.md`.
The rules here should be reusable across agent types; skills and other metadata decide which S3 areas matter for a given task.

---

## 1. Shared Source Material Storage (Authoritative Inputs)

Purpose:
Long-lived, human-curated or system-managed source material shared across agents.

Structure:

```text
s3://<shared-bucket>/
└── <env>/
    └── <source-area>/
        └── <version>/
            ├── primary-source.ext
            ├── supplementary-source.ext
            ├── rules.ext
            └── notes.ext
```

Notes:

- These objects are NOT written by agents
- Agents may only READ from this area
- Version selection rules apply (see below)
- This area is the authoritative source for shared input material, not a request workspace
- The exact `<source-area>` naming convention should be defined by the relevant metadata file or request context

Examples of source material:

- transformation documents
- coding specifications
- interview packs
- reference notes
- validation rules

---

## 2. Agent Request Storage (Request-Scoped, Agent-Owned)

Purpose:
Ephemeral, request-scoped artifacts created by agents during execution.

Structure:

```text
s3://<shared-bucket>/
└── <env>/
    └── agents/
        └── <agent-name>/
            └── requests/
                └── <request_id>/
                    ├── request/
                    ├── evidence/
                    ├── work/
                    └── deliverables/
```

Folder semantics are identical to local storage.
`request/`, `evidence/`, `work/`, and `deliverables/` must mean the same thing in S3 as they do in local request storage.
Skills must not introduce alternate S3 request layouts.
When a workflow uses both local request storage and S3 request storage, they should behave as mirror images of the same request state rather than two independent structures.

---

## 3. Retrieval & Staging Rules

When agents retrieve source material from S3:

- Search the canonical source path defined by the relevant metadata first
- Prefer the path or version explicitly requested by the user or already resolved in request context
- If the version is ambiguous, do not silently choose one for work that depends on authoritative input selection
- Stage selected files under:

```text
evidence/source-material/<source-area>/
```

Rules:

- Preserve original filenames
- Preserve bucket, prefix, and version provenance
- Do NOT modify contents
- Do not store retrieved source documents in `work/` or `deliverables/`
- If additional machine-readable summaries are needed, create them separately under `work/`

---

## 4. Provenance Requirements

For every staged S3 retrieval, agents should preserve enough information to reconstruct where the file came from.

At minimum, provenance should make it possible to identify:

- bucket
- environment prefix
- source area or source identifier
- selected version
- original key or prefix

Provenance may be captured via preserved path structure, companion metadata files, or both.
The evidence copy itself must remain unmodified.

---

## 5. Local And S3 Mirroring Rule

When a request writes artifacts locally and also persists request artifacts to S3, the S3 request area should mirror the local request structure for the same request.

This means:

- the same request identity should be used in both places
- the same `request/`, `evidence/`, `work/`, and `deliverables/` semantics should apply
- files should not be written into ad hoc locations locally while a different structure is used in S3
- agents should treat a missing mirror update as an incomplete workflow state when the current workflow expects mirroring

This file defines the mirroring expectation for S3-backed request storage.
It does not require every workflow to use S3, but when S3 mirroring is part of the workflow it must remain structurally aligned.

---

## 6. Version Selection Rules

- Prefer explicitly requested versions
- If multiple versions exist and none is specified:
  - Treat the selection as unconfirmed
  - Ask for confirmation before creating final deliverables or taking version-dependent action
- Prefer complete document sets over partial uploads

---

## 7. Retrieval Priorities

When a skill directs the agent to S3, the skill is only identifying the relevant source area.
The agent must still follow the retrieval and staging rules in this file.

Recommended retrieval order:

1. Explicit user-provided environment, source identifier, and version
2. Resolved request context already captured under `request/`
3. Canonical source-material path for the target environment
4. Broader search only when the canonical path is incomplete or missing

If the search broadens beyond the canonical path, the agent should record that fact in request context or work artifacts.

---

## 8. Retention & Lifecycle Guidance (Recommended)

- `request/` and `deliverables/` -> long retention (audit & traceability)
- `work/` -> medium retention
- `evidence/` -> shortest retention, unless required for compliance

Lifecycle policies should be applied by prefix.
