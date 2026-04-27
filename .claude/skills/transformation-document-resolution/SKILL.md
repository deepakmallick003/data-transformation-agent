---
name: transformation-document-resolution
description: Resolve, group, and stage the transformation document set needed for a request. Use when code generation depends on finding the right transformation documents from the current request or permitted external sources.
---

# Transformation Document Resolution

## Purpose

Use this skill to identify, verify, and present the correct transformation document set for a
request before any implementation work begins.

This skill is about:

- finding candidate transformation documents
- deciding which files belong to the same transformation request
- handling single-document and multi-document cases
- presenting the selected document set to the user in a structured way when confirmation is required
- preparing the approved document set for downstream use in the local storage model defined by `CLAUDE.md`

Do not generate transformation logic here beyond what is needed to justify document selection.
Do not define alternate storage semantics here. Use the request storage contract from `CLAUDE.md`
and any applicable source metadata such as `s3_structure.md`.

## Use This Skill When

- the request references a transformation but the document set is not yet assembled
- the relevant files may exist in the current request or metadata-backed source locations
- a transformation may have more than one supporting document
- the agent may need to search permitted external sources and stage the results locally
- downstream code generation should work from a stable staged document set instead of ad hoc file paths

## Resolution Priorities

Search in this order unless the user gives a better instruction:

1. documents already provided directly in the current request
2. uploaded files in the current request
3. relevant metadata that describes where to search in S3
4. permitted S3 sources when the document set was not provided directly

## Confirmation Boundary

Use this decision rule before handing off to code generation:

- if the user pasted the transformation document content directly in the current request, that is confirmed evidence
- if the user uploaded the transformation documents directly in the current request, that is confirmed evidence
- if the agent had to discover candidate documents from external sources, treat the result as unconfirmed until the user approves that document set

Do not move from discovered documents to code generation without a user green light when the
documents were not directly provided in the current request.
If confirmation is required and has not been received, stop after presenting the candidate set.

## What Counts As A Document Set

A transformation request may require one document or a related set of documents.

Treat these as belonging together when they share the same transformation identity, feed identity,
source-target pairing, request identifier, or mutually reinforcing references:

- transformation document
- feed specification document
- interdependencies or lineage document
- mapping or rule supplements
- validation, rejection, or operational notes

Do not assume one file is sufficient just because it contains the word "transformation."

## Operating Mode

Use one of these two modes:

- human-in-the-loop mode: the default. Present discovered sets and wait for user confirmation before staging or handoff when the set was not directly supplied in the current request.
- unattended mode: only when the runtime or caller has explicitly configured the agent to operate without user confirmation. In this mode, make the most defensible deterministic choice, record that choice clearly, and continue only if all validation gates pass.

Prefer deliberate grouping over broad collection. The goal is the right set, not every nearby file.

## Phase Contract

Follow these phases in order. Do not skip ahead.

1. Discover candidate files and group them into plausible document sets.
2. Validate grouping quality, completeness, and request relevance.
3. Decide whether user confirmation is required.
4. If confirmation is required, present the candidate set or sets in a structured format and stop.
5. Only after approval, stage the approved set according to `CLAUDE.md` and the relevant source metadata.
6. Re-validate the staged result before handing off.

## Working Method

1. Extract the strongest available identifiers from the request.
2. Read the relevant metadata files that explain candidate source locations, naming conventions, and bucket prefixes.
3. Search for candidate documents using filenames, feed references, request ids, source and target system names, and transformation slugs.
4. Read enough of each candidate to confirm scope, ownership, and whether it belongs to the same transformation.
5. Group documents into the smallest complete set that can credibly support implementation.
6. If multiple plausible sets exist, rank them by evidence strength and completeness instead of silently choosing one.
7. Determine whether confirmation is required under the rules above.
8. If confirmation is required, present the findings and stop until the user chooses or approves a set.
9. If confirmation is not required, or has been received, stage the approved set using the local storage contract.
10. Validate that the staged result satisfies the local structure before handoff.

## Selection Rules

- Use explicit identifiers first: request id, feed reference, transformation name, source system, target system.
- Use internal cross-references next: one document naming another, shared version markers, matching dates, or shared table and file names.
- Prefer document completeness over recency when newer files are obviously partial drafts.
- Prefer source documents over screenshots or secondary summaries when both exist.
- Keep related documents together even if they live in different source locations before staging.
- Do not silently merge different transformations that merely share a domain or system.
- If the chosen set comes from agent discovery rather than direct user evidence, show the user exactly which files are about to be used.
- If multiple plausible sets remain, do not auto-pick in human-in-the-loop mode. Present numbered options.

## External Search Rules

Only use tools and locations the agent is permitted to access.

- Check the current request first.
- Use the relevant metadata file first when it narrows the external search space, such as `s3_structure.md`, table definitions, or source-layout notes.
- If remote retrieval is needed, use the relevant permitted search or retrieval tool for that source.
- Prefer the most direct allowed tool for the source rather than forcing a fixed integration pattern.
- Bring remote files into the request-scoped `request/` area defined by `CLAUDE.md`.
- Preserve the original filename where practical.

If access is blocked or approval is required, say so clearly instead of pretending the search is complete.

## Search Scope Discipline

Prefer the current request and configured S3 sources over any broader search.

- treat metadata files as discovery aids and source descriptors, not as the transformation document set itself unless a metadata file is itself the requested source document
- treat reusable templates or scaffolding areas as references, not as the transformation document set itself unless the user explicitly says otherwise

## Structured User Presentation

When user confirmation is required, present findings in a disciplined format.

For a single plausible discovered set, show:

- the proposed transformation or feed identity
- the files in the set
- why this set was selected
- any missing or ambiguous pieces
- a direct approval question

For multiple plausible sets, show:

- numbered options
- the files in each option
- why each option is plausible
- what makes one option stronger or weaker than another
- a direct choice prompt

Do not proceed to staging for downstream generation in human-in-the-loop mode until the user has
approved the set or selected an option.

## Staging

After approval, stage the selected documents using the request storage semantics from `CLAUDE.md`.

Use `request/` exactly as defined there for the resolved document set.
Do not invent alternate folder structures inside this skill.

For this skill specifically:

- store fetched source documents under request-scoped `request/`
- keep original filenames where practical
- keep grouped documents together under a stable source-specific subpath

The staged set should be clean enough that downstream implementation work can consume it without
re-running discovery.

## Handoff To Code Generation

Before handing off to Python generation, make sure the staged set is usable as an implementation
input.

- the chosen document set should be complete enough to support grounded code generation
- the primary transformation document should be obvious from the staged folder contents
- supporting documents should remain alongside it rather than being scattered
- any missing or conflicting documents should be called out explicitly for the next skill
- if the document set was agent-discovered, the user should have explicitly confirmed that this is the set to use
- the request-scoped structure should satisfy the local contract from `CLAUDE.md`

## Validation Gates

Do not proceed or claim completion if any of these fail:

- required user confirmation is missing
- the selected set still has unresolved identity conflicts
- the staged documents are not stored under the local request structure
- files have been written into a loose unstructured area outside the local request structure

## Done When

This skill has done its job when:

- the relevant transformation document set has been identified
- the selected files are grouped as one approved document set
- any required user confirmation has been obtained before generation proceeds
- the approved set has been staged under the local request structure from `CLAUDE.md`
- the grouped document set is clear enough for downstream review
- the next skill can use the staged set without needing to rediscover documents
- any missing, conflicting, or inaccessible documents are called out explicitly
