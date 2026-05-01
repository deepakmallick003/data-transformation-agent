---
name: transformation-document-resolution
description: Resolve, group, confirm, and stage the document set needed for a transformation request before implementation begins.
---

# Transformation Document Resolution

## Purpose

Use this skill to find the right transformation document set, confirm it when needed, and stage it
for downstream implementation.

## When To Use

Use this skill when:

- the request references a transformation but the document set is not yet assembled
- multiple related files may belong to the same transformation
- the agent needs to search permitted S3 sources or metadata-backed locations
- downstream generation should work from a stable staged set instead of ad hoc paths

## Inputs

Read only the inputs needed to identify the correct set:

- files pasted or uploaded in the current request
- relevant metadata files such as `s3_structure.md`
- permitted S3 source files when discovery is required

## Tool Use

- use `list_s3_objects` to discover candidate files in configured S3 sources
- use `read_s3_object` to inspect selected S3 files
- use `write_request_s3_file` only when you need request-scoped staged output to be tool-managed
- do not invent raw bucket paths or raw S3 prefixes in this skill

## Storage Rules

- `CLAUDE.md` defines the file contract
- stage approved source files under `request/`
- external tool writes are allowed in this skill only for request-scoped staging
- when staging with `write_request_s3_file`, set `folder="request"`
- use `storage_mode="local"` by default
- override to `storage_mode="mirror"` when the user wants both local and S3 copies
- override to `storage_mode="s3"` only when the user wants S3-only persistence or the workflow clearly requires it
- use a small `relative_path` only when it helps keep related source files grouped
- do not promise arbitrary user-local destinations unless a dedicated tool exists for that destination

## Stages

### Stage 1: Discover

Search in this order unless the user gives a better instruction:

1. documents provided directly in the current request
2. files uploaded in the current request
3. metadata that narrows the search space
4. permitted external S3 sources using `list_s3_objects`, then `read_s3_object` on shortlisted files

### Stage 2: Group

Group the smallest complete set that can credibly support implementation.

Usually keep together:

- transformation document
- feed specification
- interdependencies or lineage notes
- mappings or rule supplements
- validation or operational notes

### Stage 3: Validate

Check:

- transformation identity
- source and target pairing
- completeness
- conflicting versions
- whether the files really belong together

### Stage 4: Confirm

If the set was discovered externally rather than supplied directly by the user, require explicit
user approval before handoff to code generation.

If confirmation is required, stop after presenting the candidate set.

### Stage 5: Stage

After approval, stage the selected set into `request/`.

- preserve original filenames where practical
- keep grouped files together with a small relative subpath when helpful, such as `source-docs/`
- if you use the storage tool, explicitly choose `storage_mode` instead of relying on inference
- do not invent a separate storage layout outside the file contract

### Stage 6: Handoff

Leave the staged set in a shape that downstream generation can use without repeating discovery.

## Decision Rules

- prefer explicit identifiers first: request id, feed reference, transformation name, source system, target system
- prefer direct source documents over screenshots or summaries
- prefer completeness over recency when the newer file is clearly partial
- do not silently merge different transformations just because they share a domain
- if multiple plausible sets remain in human-in-the-loop mode, present options instead of guessing
- in unattended mode, make the most defensible deterministic choice and record it clearly

## User Choice Format

When you need user input, use this format:

- if there is one plausible option, ask for approval in one short line:
  approve this set? `yes` or `no`
- if there are multiple plausible options, present numbered options in this format:
  `Option 1:` one-line label
  `Why:` one short reason
  `Tradeoff:` one short tradeoff
- end with one direct choice prompt:
  reply with `1`, `2`, `3`, or `stop`

## Done When

This skill is complete when:

- the right transformation document set has been identified
- any required user approval has been obtained
- the approved files are staged under `request/`
- unresolved gaps or conflicts are called out clearly for the next skill
