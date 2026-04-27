---
name: transformation-documents-to-python
description: Read a staged transformation document set and generate grounded Python implementation output from it. Use when the goal is to turn transformation documents into executable Python code.
---

# Transformation Documents To Python

## Purpose

Use this skill to convert a staged transformation document set into Python implementation output.

This skill is about:

- reading the relevant document set as a whole
- extracting mappings, rules, dependencies, validations, and rejection logic
- identifying implementation decisions that still require user choice
- choosing a deterministic Python implementation shape only after the choice boundary is resolved
- generating grounded code and related runtime artifacts using the shared storage contract from `CLAUDE.md`

Do not invent business logic that the documents do not support.
Do not stop at a raw script if the output would be hard to run, review, or test.
Do not define alternate storage policy here. Use the shared storage and mirroring rules from
`CLAUDE.md` and the relevant metadata such as `s3_structure.md`.

## Use This Skill When

- the relevant transformation documents have already been resolved and staged
- the user wants Python implementation output from those documents
- the implementation needs to reflect multiple related documents, not just one file
- the code should stay grounded in the document evidence

If document resolution is still uncertain, use `transformation-document-resolution` first.
If the document set was discovered by the agent rather than directly supplied in the current
request, require explicit user confirmation before generating code.

## Operating Mode

Use one of these two modes:

- human-in-the-loop mode: the default. Ask the user to resolve meaningful implementation choices before generating code.
- unattended mode: only when the runtime or caller has explicitly configured the agent to operate independently. In this mode, choose from the default design profiles below, record those choices clearly, and continue only if all validation gates pass.

## Inputs To Read

Read the full staged set, not just the main transformation document.

Look for:

- source file definitions and expected inputs
- target schema or output expectations
- field mappings and derivations
- normalization rules and defaults
- validations and rejection conditions
- dependency ordering, joins, and reference data needs
- runtime or batch assumptions such as schedule, incrementality, or load keys

Treat specification, transformation, and interdependency documents as complementary evidence.

## Source Gate

Only proceed directly to code generation when one of these is true:

- the user pasted the document contents directly in the current request
- the user uploaded the documents directly in the current request
- the user explicitly confirmed the discovered staged document set

If none of those conditions is true, stop after document resolution and ask for confirmation rather
than generating code from a guessed or auto-selected document set.

## Design Decision Boundary

Do not move straight from reading documents to generating code when meaningful design choices remain open.

Meaningful choices may include:

- single script or multi-file package
- CLI-only or service/API-oriented wrapper
- minimal dependency set or broader library usage
- whether tests should be generated
- whether sample or fixture data should be generated
- whether the output should be script-only, a runnable project, or a handoff bundle

If the documents or request clearly determine the answer, follow that evidence.
If they do not, and the agent is in human-in-the-loop mode, ask the user before generating code.

## Structured User Questions

In human-in-the-loop mode, ask a small, focused set of implementation questions when the answer is not already clear.

Keep the questions concise and decision-oriented.
Do not ask for every possible preference.
Ask only what materially affects structure, dependencies, deliverables, or runtime shape.

Typical examples include:

- should this be a single script or a small multi-file project
- do you want a plain script, CLI-friendly package, or API/web wrapper
- should I generate tests and sample test data
- should I stay with lightweight dependencies unless the documents clearly require more

If multiple options are plausible, present them as clear choices with a short implication for each.
Do not generate code until the needed choices are resolved, unless unattended mode has been explicitly enabled.

## Default Design Profiles

When unattended mode is explicitly enabled, choose only from these deterministic implementation profiles:

- `script-basic`: one primary Python script, minimal dependencies, no generated tests unless clearly needed
- `script-plus-tests`: one primary Python script with focused tests and basic fixtures
- `package-cli`: small package with reusable modules and a thin CLI entrypoint
- `package-api`: small package with clear service boundaries for API-style exposure when the request or documents justify it

Prefer the lightest profile that credibly satisfies the request and documents.
Do not invent a custom architecture when one of these profiles is sufficient.

## Working Method

1. Read the staged document set and identify the implementation boundary.
2. Confirm that the document set is approved for use if it was agent-discovered.
3. Extract explicit source-to-target mappings, rule logic, validations, and failure paths.
4. Assess whether the document set is sufficient for a fully runnable implementation or only a bounded best-effort slice.
5. Separate confirmed logic from assumptions or gaps.
6. Identify which implementation decisions are already determined by the documents and which still need a choice.
7. If human-in-the-loop mode applies and unresolved meaningful choices remain, ask the user and stop until those choices are answered.
8. Choose the lightest credible implementation profile from the approved or default options.
9. Generate Python code that implements the confirmed behavior first.
10. Validate the generated code before finalizing it.
11. Add the supporting run guidance needed to make the output usable.
12. Generate supporting configuration artifacts only when the document set or chosen profile implies they are needed.
13. Make assumptions visible in comments or a short module docstring instead of burying them in logic.
14. Store the generated outputs using the shared storage contract from `CLAUDE.md`.
15. Package the generated bundle when the workflow or user would benefit from a handoff-ready artifact.

Prefer a clear working implementation over a large speculative framework.

## Implementation Shape Guidance

Choose the implementation shape that best matches the documents and the resolved user choices:

- file-to-file transformation script for feed-based CSV or delimited inputs
- reusable parser and transformer module when multiple source files feed one output flow
- validation-first pipeline when rejection logic is prominent
- staged transformation functions when dependencies or enrichment steps are explicit
- YAML configuration or contract artifact when the workflow needs structured runtime metadata alongside the code

Prefer standard-library Python unless the documents clearly justify heavier dependencies.
If dependency choice is materially open and human-in-the-loop mode applies, ask before adding broader libraries.

## Verification Rule

Do not finalize generated code without checking that it is syntactically valid and runnable to the
extent feasible in the current environment.

- run a syntax check or equivalent static validation on generated Python
- run tests, smoke checks, or a minimal execution path when feasible
- exercise at least one representative transformation path with realistic fixture data for the core mapping, normalization, and validation logic
- for scripts that depend on external systems, validate the internal transformation path with mocked or local fixture inputs rather than relying only on `--help`, import success, or connector setup
- if validation fails, fix the code and re-run validation before presenting it as finished
- do not leave the user with a script that is known to be broken
- if execution cannot be completed because inputs, credentials, services, or tooling are missing, state that explicitly in the support files

Prefer small verifiable deliverables over large unverified ones.

## Self-Validation Checklist

Before completing the skill, verify all of the following:

- the document set was approved for generation
- required user design choices were resolved, or unattended mode was explicitly enabled
- the selected implementation profile matches the request and documents
- the generated files are stored under the shared request structure from `CLAUDE.md`
- files were not dumped loosely into an unstructured location outside the shared request structure
- any required local-to-S3 mirroring expectations have been satisfied for this workflow
- the generated code passed the feasible validation checks
- the support files accurately describe assumptions and gaps

If any item fails, do not proceed as if the skill completed successfully.

## Python Code Standard

Generated Python should be production-minded, readable, and easy to review.

- follow normal Python conventions such as clear module structure, small functions, and descriptive names
- prefer type hints on public functions and data structures
- keep configuration separate from transformation logic where practical
- use explicit parsing, validation, and error handling rather than silent fallbacks
- avoid hard-coded paths, credentials, and environment-specific values
- use lightweight logging or clear status output for meaningful processing steps
- keep comments concise and evidence-linked rather than narrating obvious code

Prefer plain, testable Python over framework-heavy scaffolding.

## Adaptation For External Systems

Do not assume every transformation is local file to local file.

If the document set indicates cloud systems, databases, APIs, object storage, knowledge bases, or
other external platforms, adapt the generated implementation accordingly.

- include connector functions or adapter modules when the transformation depends on external systems
- use environment variables or explicit configuration files for connection details, endpoints, bucket names, database names, schema names, credentials by reference, and runtime flags
- keep business logic separate from connection setup so the transformation remains testable
- fail fast with clear error messages when required configuration is missing
- avoid embedding secrets, fixed hostnames, or repo-specific paths in generated code

Examples of scenarios that should trigger this behavior include:

- source data in PL/SQL-backed systems or cloud databases
- targets in S3 or equivalent object storage
- targets in vector stores, search indexes, or knowledge bases
- source or target access through SDKs, JDBC/ODBC layers, REST APIs, or platform clients

## Grounding Rules

- Every major transformation step should be traceable to something stated or strongly implied in the document set.
- Do not fabricate join keys, default values, or target fields that are not supported.
- If a required detail is missing, leave a clear assumption or a deliberate placeholder rather than pretending certainty.
- Keep rejection and validation logic aligned with the documented rules.
- Preserve business terminology from the documents where that improves clarity.
- Do not treat agent-discovered documents as implicitly approved just because they look plausible.

When documents conflict, implement only the defensible core and call out the conflict explicitly.

## Sufficiency Assessment

Before finalizing generated code, decide which of these cases applies:

- fully runnable from the document set as written
- runnable with bounded local assumptions that are documented clearly
- not runnable without missing external details, contracts, or runtime assets

If the documents do not support a full production-faithful implementation, still produce the best
grounded runnable slice you can, but make the operational gap explicit in the generated support
files.

Missing details should be surfaced clearly rather than silently papered over. User-facing gaps
should be explained in the generated `README.md`, which should distinguish:

- implemented behavior grounded in the documents
- bounded assumptions added to make the script runnable
- missing operational details that block a production-faithful implementation
- optional future enhancements that were intentionally not invented

## Output Handling

Write generated outputs using the shared storage contract from `CLAUDE.md`.
Do not define a competing output layout in this skill.

For this skill:

- generated code and support files belong in request-scoped `deliverables/`
- staged source documents remain under `request/`
- if packaging is required, the package should reflect the deliverables exactly
- if local request artifacts are mirrored to S3 for this workflow, ensure the mirrored state stays aligned before completion

Keep the output paths deterministic within the shared request structure so downstream steps can reference them reliably.

## Supporting Files

The deliverable set should usually contain more than the Python file itself.

### `README.md`

Create a concise request-specific `README.md` that explains:

- what the script does
- which staged transformation documents it was derived from
- expected input files or directories
- required environment variables if any
- how to run the script
- known assumptions or unresolved gaps

Write the run instructions so the deliverable can be extracted and executed from any directory, not only
from the repository that generated it.
Do not expose internal skill-selection details or generation-process commentary in this file.
If the request-scoped staged documents live outside the deliverable folder, describe that clearly in
user-facing terms instead of assuming sibling folders that may not exist after packaging.

### `.env.example`

Create `.env.example` when the generated code expects environment variables, external locations,
credentials by reference, or runtime configuration that should not be hard-coded.

Include placeholders only, such as input paths, output paths, bucket names, prefixes, or runtime
flags. Do not place secrets in generated files.

If no environment variables are needed, do not create `.env.example` just for symmetry.

When external systems are involved, `.env.example` should usually be paired with concise guidance in
`README.md` describing which variables are mandatory and what each one controls.

### YAML configuration artifact

Create a YAML artifact when the transformation documents imply a structured runtime contract,
configuration file, feed definition, orchestration input, or schema-like metadata artifact.

- do not hard-code the filename as `feed.yaml`
- choose a sensible request-specific name such as `<transformation-slug>.yaml`, `feed-config.yaml`, or `transformation-config.yaml`
- keep the YAML grounded in the documents, just like the generated Python
- use it for structured metadata such as inputs, outputs, dependencies, runtime settings, validation expectations, or connector configuration
- if no YAML-shaped artifact is implied by the documents or workflow, do not create one just for symmetry

## Packaging

When the generated output is intended for handoff, delivery, or download, provide a single bundled
artifact at the request level or another nearby handoff location.

- prefer a zip archive of the generated script and supporting files
- ensure the archive contents match the staged outputs exactly
- include supporting files only when they are needed for delivery
- include the source documents themselves only when the workflow explicitly requires a self-contained bundle and doing so does not violate the shared storage contract
- reuse the already-staged request evidence rather than creating loose duplicate copies in unrelated working locations
- do not omit `README.md`, YAML configuration artifacts, or required configuration examples from the archive when they are part of the deliverable
- exclude transient artifacts such as `__pycache__`, compiled bytecode, temporary outputs, or local editor files
- ensure the archive remains usable when extracted outside the original repository
- if a single-file deliverable is explicitly required, prefer one self-contained Python script and keep supporting guidance minimal but still present where possible

## Testability Standard

The generated implementation should be easy to test during generation.

- separate pure transformation logic from CLI or file-system wiring where practical
- prefer deterministic functions that accept explicit inputs and return explicit outputs
- make validation and rejection logic observable in tests
- avoid hiding core rules inside `main()` only
- derive tests from documented mappings, validation rules, and rejection scenarios where evidence exists

Run validation and tests while generating the code, but do not assume test files must be shipped in
the final user-facing bundle unless the user explicitly asks for them.

## Execution Shape

When the documents support a script-style deliverable, prefer a structure like:

- parsing and input loading
- normalization and field mapping
- validation and rejection handling
- output writing
- a thin `main()` or CLI entrypoint

Keep the orchestration thin and the business rules concentrated in reusable functions.

## Code Expectations

The generated Python should:

- make inputs and outputs explicit
- implement mappings and derivations clearly
- apply validation and rejection logic in code, not just comments
- reflect dependency order where the document set requires it
- be runnable with the documented setup
- be testable without rewriting the whole script
- avoid unsupported optimizations or architecture flourishes

Include concise comments only where they help connect tricky logic to the document evidence.

## Done When

This skill has done its job when:

- the staged document set has been read as one implementation input
- the document source is direct or explicitly user-confirmed
- any required design choices have been resolved or explicitly defaulted under unattended mode
- the generated Python reflects the documented mappings and rules
- assumptions and unresolved gaps are visible instead of hidden
- the generated artifacts live under the shared request structure from `CLAUDE.md`
- any needed environment template is included without exposing secrets
- the output is structured so another engineer can run and test it
- a single bundled artifact is produced when handoff packaging is useful
- the workflow has not violated any shared storage or mirroring rule
- another engineer can see how the code connects back to the transformation documents
