---
name: transformation-document-resolution
description: Resolve, group, and stage the transformation document set needed for a request. Use when code generation depends on finding the right transformation documents locally or from permitted external sources.
---

# Transformation Document Resolution

## Purpose

Use this skill to identify the correct transformation document set for a request before code is
generated.

This skill is about:

- finding candidate transformation documents
- deciding which files belong to the same transformation request
- handling single-document and multi-document cases
- staging the chosen document set into a clean local structure for downstream use

Do not generate transformation logic here beyond what is needed to justify document selection.

## Use This Skill When

- the request references a transformation but the document set is not yet assembled
- the relevant files may exist in multiple local folders or upstream staged handoff areas
- a transformation may have more than one supporting document
- the agent may need to search permitted external sources and stage the results locally
- downstream code generation should work from a stable staged document set instead of ad hoc file paths

## Resolution Priorities

Search in this order unless the user gives a better instruction:

1. documents already provided directly in the current request
2. uploaded files or explicitly designated source or staging locations for this workflow, including sample-data areas when the request is for testing or simulation
3. known upstream handoff locations, only when this workflow is expected to receive staged transformation documents from an earlier step
4. permitted external sources, only when the document set cannot be resolved locally

Prefer the closest evidence to the current request. Do not ignore a direct user-provided document
because an older local copy also exists.

Do not broadly treat `data/results/` as a generic search area just because it contains past outputs.
Use it only when it is acting as a deliberate staged handoff location in the wider workflow.

## Confirmation Boundary

Use this decision rule before handing off to code generation:

- if the user pasted the transformation document content directly in the current request, that is confirmed evidence
- if the user uploaded the transformation documents directly in the current request, that is confirmed evidence
- if the agent had to discover candidate documents from local history, prior staged outputs, or external sources, treat the result as unconfirmed until the user approves that document set

Do not move from discovered documents to code generation without a user green light when the
documents were not directly provided in the current request.

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

## Working Method

1. Extract the strongest available identifiers from the request.
2. Search for candidate documents using filenames, feed references, request ids, source and target system names, and transformation slugs.
3. Read enough of each candidate to confirm scope, ownership, and whether it belongs to the same transformation.
4. Group documents into the smallest complete set that can credibly support implementation.
5. If multiple plausible sets exist, prefer the one with the strongest direct evidence and most complete coverage.
6. Stage the selected set into a request-specific local folder for downstream use.
7. If the selected set was agent-discovered rather than directly provided by the user, present the planned document set and source locations for confirmation before code generation.

Prefer deliberate grouping over broad collection. The goal is the right set, not every nearby file.

## Selection Rules

- Use explicit identifiers first: request id, feed reference, transformation name, source system, target system.
- Use internal cross-references next: one document naming another, shared version markers, matching dates, or shared table and file names.
- Prefer document completeness over recency when newer files are obviously partial drafts.
- Prefer staged markdown or source documents over screenshots or secondary summaries when both exist.
- Keep related documents together even if they live in different source locations before staging.
- Do not silently merge different transformations that merely share a domain or system.
- If the chosen set comes from agent discovery rather than direct user evidence, show the user exactly which files are about to be used and from where.

## External Search Rules

Only use tools and locations the agent is permitted to access.

- Search locally first.
- If remote retrieval is needed, use the relevant permitted search or retrieval tool for that source.
- Prefer the most direct allowed tool for the source rather than forcing a fixed integration pattern.
- Bring remote files into the local staged folder before downstream processing.
- Preserve the original filename where practical.
- Record enough provenance to explain where each staged file came from.

If access is blocked or approval is required, say so clearly instead of pretending the search is complete.

## Search Scope Discipline

Prefer designated source or handoff locations over broad output scanning.

- do not treat historical outputs as the default source of truth
- do not search `data/results/` indiscriminately for candidate documents
- use `data/results/` only when upstream workflow behavior intentionally stages transformation documents there
- treat `data/sample-data/` or similar sample-document locations as valid sources when the task is clearly a test, simulation, or example-driven run
- if the repository has templates such as `data/templates/` or other reusable pattern areas, treat them as references or scaffolding, not as the transformation document set itself unless the user explicitly says otherwise

## Staging Layout

Stage the selected documents under a disciplined results location such as:

```text
data/
  results/
    request<request_id>/
      transformation-documents/
        <transformation-slug>/
          ...
```

If no request id exists, generate one and still use the same request-style pattern, for example:

```text
data/
  results/
    request<generated_id>/
      transformation-documents/
        <transformation-slug>/
          ...
```

Use a stable slug based on the best confirmed transformation identity, such as
`etmp-to-mdm-vat` or `vat-returns-feed`.
If no request id is supplied by the workflow, generate one and keep the outer folder in the
`request<id>` pattern for consistency across runs.

Inside the staged folder:

- keep original filenames when they are already meaningful
- avoid renaming files in ways that hide their source role
- keep all documents for the same transformation together
- create a brief manifest only when provenance or grouping would otherwise be ambiguous
- prefer deterministic folder naming; use a request id when available, otherwise generate one and keep the `request<id>` pattern

The staged set should be clean enough that downstream code generation can consume it without
re-running discovery.

## Handoff To Code Generation

Before handing off to Python generation, make sure the staged set is usable as an implementation
input.

- the chosen document set should be complete enough to support grounded code generation
- the primary transformation document should be obvious from the staged folder contents
- supporting documents should remain alongside it rather than being scattered
- any missing or conflicting documents should be called out explicitly for the next skill
- if a manifest is needed, it should clarify grouping and provenance, not restate the documents
- if the document set was agent-discovered, the user should have explicitly confirmed that this is the set to use

## Done When

This skill has done its job when:

- the relevant transformation document set has been identified
- the selected files are grouped as one staged document set
- the staged location is stable and request-specific
- the agent can hand the staged set to Python code generation without needing to rediscover documents
- any required user confirmation has been obtained before generation proceeds
- any missing, conflicting, or inaccessible documents are called out explicitly
