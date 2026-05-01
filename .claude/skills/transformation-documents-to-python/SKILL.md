---
name: transformation-documents-to-python
description: Read a staged transformation document set and generate grounded Python deliverables from it.
---

# Transformation Documents To Python

## Purpose

Use this skill to turn an approved staged document set into runnable, reviewable Python
deliverables.

## When To Use

Use this skill when:

- the relevant transformation documents have already been resolved and staged
- the user wants Python output derived from those documents
- the implementation must stay grounded in the staged evidence

If the document set is still uncertain, use `transformation-document-resolution` first.

## Inputs

Read the staged set as a whole, not only the main document.

Look for:

- source inputs and target outputs
- mappings and derivations
- normalization rules and defaults
- validation and rejection logic
- dependencies, joins, enrichments, or reference data
- runtime assumptions and external-system requirements

## Tool Use

- use normal local `Write` for local output when that is sufficient or when the user explicitly asks for a specific folder inside the local workspace
- use `write_request_s3_file` when deliverables must be tool-managed, mirrored to S3, or written as S3-only artifacts
- do not invent raw bucket paths or raw S3 prefixes in this skill

## Storage Rules

- staged source files remain under `raw/`
- generated outputs belong under `processed/`
- external tool writes are allowed in this skill only for request-scoped deliverables
- when using `write_request_s3_file` for generated artifacts, set `folder="processed"`
- use `storage_mode="local"` by default
- override to `storage_mode="mirror"` when the user wants both local and S3 copies
- override to `storage_mode="s3"` only when the user wants S3-only persistence or the workflow clearly requires it
- use `relative_path` to place files into a specific subdirectory inside the managed `processed/` location, such as `handoff/` or `tests/`
- if the user explicitly asks for a specific local repo/workspace directory, use `Write` for that exact local path
- do not promise destinations outside the accessible local workspace or outside the configured agent-scoped S3 write area

## Stages

### Stage 1: Confirm Source Readiness

Proceed only when one of these is true:

- the user pasted the documents directly
- the user uploaded the documents directly
- the user explicitly approved the discovered staged set

If not, stop and return to document resolution.

### Stage 2: Extract Confirmed Logic

Separate:

- confirmed mappings and rules
- bounded assumptions needed for a runnable implementation
- missing or conflicting details that must be surfaced clearly

Do not invent unsupported business logic.

### Stage 3: Resolve Material Choices

Ask the user only about choices that change structure or deliverables, for example:

- single script or small package
- plain script, CLI wrapper, or API-style wrapper
- whether tests should be generated
- whether lightweight dependencies should be preserved

If unattended mode is explicitly enabled, choose the lightest credible option and record it clearly.

### Stage 4: Generate Deliverables

Create the smallest credible set of deliverables under `processed/`.

Usually include:

- Python implementation
- request-specific `README.md`

Add only when justified:

- `.env.example`
- YAML configuration artifact
- tests or fixtures
- zip handoff bundle

When you use the storage tool, explicitly choose `storage_mode` instead of relying on inference.

### Stage 5: Validate

Before finishing:

- run a syntax check on generated Python
- run tests or a small smoke path when feasible
- if runtime dependencies are unavailable, validate the internal transformation logic as far as possible and say what could not be executed

If validation fails, fix the code before finishing.

### Stage 6: Package

If the user needs a handoff bundle, package the generated deliverables exactly as staged.

- keep the archive aligned with `processed/`
- exclude transient artifacts such as `__pycache__`
- include supporting files that are needed to run or review the output

## Decision Rules

- prefer the lightest implementation shape that credibly satisfies the request
- prefer standard-library Python unless the documents clearly justify more
- keep business logic separate from connector or environment setup
- when external systems are involved, use environment variables or explicit config files rather than hard-coded values
- if the documents do not support a production-faithful implementation, produce the best grounded runnable slice and document the gap clearly

## User Choice Format

When user input is required, use this format:

- if there is one required decision, ask it in one short line:
  choose one: `1` or `2`
- if there are multiple plausible options, present numbered options in this format:
  `Option 1:` one-line label
  `Why:` one short reason
  `Tradeoff:` one short tradeoff
- end with one direct choice prompt:
  reply with `1`, `2`, `3`, or `stop`
- do not ask for preferences that do not materially affect structure, runtime, or deliverables

## Done When

This skill is complete when:

- the source set was valid for generation
- required user choices were resolved, or unattended mode was explicitly allowed
- deliverables were written under `processed/`
- generated code passed the feasible validation checks
- assumptions and missing operational details are described clearly in the support files
