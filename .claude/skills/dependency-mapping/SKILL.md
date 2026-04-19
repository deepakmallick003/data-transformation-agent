---
name: dependency-mapping
description: Build a working map of upstream inputs, joins, sequencing, controls, downstream consumers, and operational coupling for a transformation. Use when dependency analysis is needed and keep data-dependency-map.md implementation-grade.
---

# Dependency Mapping

## Purpose

Use this skill to expose how the transformation actually hangs together: what it depends on,
what it produces, what must happen in order, and where the fragile edges are.

Keep `data-dependency-map.md` current through the session MCP tools.

## Use This Skill When

- the source and target are understood well enough to reason about movement and dependency
- the team needs lineage, joins, sequencing, or validation logic made explicit
- there are multiple systems, files, datasets, or owners involved
- implementation risk depends on hidden couplings, upstream quality, or downstream expectations

This skill should convert "we think this uses several inputs" into an explicit dependency model
that an engineer can plan against.

## Working Method

1. Start from the current transformation understanding rather than rediscovering the request.
2. Identify all meaningful upstream inputs and what each contributes.
3. Trace how data or documents are combined, transformed, enriched, filtered, or validated.
4. Identify downstream outputs, consumers, triggers, and handoff expectations.
5. Update `data-dependency-map.md` so the dependency picture is actionable and testable.

Prefer explicit relationships over broad statements like "depends on multiple systems."

## What To Capture

### Upstream Inputs

For each upstream input, record:

- what the input is
- whether it is authoritative, optional, derived, or reference-only
- the fields, sections, or elements that matter
- how it links to other inputs
- what risk comes from lateness, absence, or low quality

### Transformation Stages

Break the flow into practical stages. Stages should reflect real implementation boundaries such as:

- ingestion
- normalization
- matching or joining
- enrichment
- rule application
- validation
- packaging or publication

For each stage, make inputs, outputs, and validation visible.

### Downstream Outputs

Describe:

- what is produced
- who consumes it
- what triggers delivery
- what format or contract matters
- what follow-on systems or teams depend on it

### Validation And Controls

Identify controls that protect correctness or trust, for example:

- schema checks
- reconciliation logic
- duplicate detection
- cross-source consistency checks
- row or record count checks
- business rule validation
- sign-off gates

Name the likely owner where possible.

## Risk And Coupling Standards

Use `Risks And Couplings` for issues that could break or complicate delivery, such as:

- hidden join keys or unstable identifiers
- unclear system ownership
- timing dependencies
- manual intervention points
- circular dependencies
- quality issues that appear upstream but surface downstream

Be direct about fragility. This document should help the team avoid surprises, not merely look complete.

## Writing Standards

When updating `data-dependency-map.md`:

- keep the dependency chain concrete and legible
- prefer one row per real dependency or stage over compressed summaries
- make joins and linkage logic explicit
- call out unknown dependencies separately from confirmed ones
- write so another engineer could turn the map into implementation tasks and tests

## Decision Rules

- if two plausible dependency paths exist, document both and state what would decide between them
- if lineage is partial, map the confirmed path and isolate the uncertain segments
- if ownership is unclear, record the uncertainty instead of inventing accountability
- if the analysis exposes approval or governance blockers, surface them for delivery planning

## Done When

This skill has done its job when:

- the upstream inputs are identifiable and differentiated
- the transformation stages are explicit
- the downstream consumers and delivery expectations are visible
- the main controls and failure points are named
- a delivery planner can sequence work without having to reverse-engineer the dependency graph
