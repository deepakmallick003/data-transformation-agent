---
name: transformation-discovery
description: Legacy compatibility wrapper for source-analysis and target-contract-analysis. Use the newer capability-oriented skills for ongoing work.
---

# Transformation Discovery

This skill remains for backward compatibility.

Prefer:

- `source-analysis`
- `target-contract-analysis`

## Purpose

Use this skill to turn an ambiguous transformation request into a working technical brief.
The output should be strong enough that dependency mapping and delivery planning can proceed
without re-discovering the basics.

Keep `transformation-understanding.md` current through the session MCP tools.

## Use This Skill When

- the user has described a migration, mapping, conversion, ingestion, export, or system-to-system change
- uploaded files or notes contain partial clues that need to be synthesized into one coherent view
- the source, target, format, ownership, or constraints are still incomplete or scattered
- the team needs a crisp statement of what is known, what is assumed, and what still blocks progress

Do not stay in discovery longer than necessary. Once the request is understood well enough,
hand off cleanly to dependency mapping or delivery planning.

## Working Method

1. Read the available session context first.
2. Inspect uploaded material, notes, templates, and prior artifacts before making assumptions.
3. Identify the transformation objective in practical engineering terms.
4. Extract source facts, target facts, constraints, assumptions, and missing information.
5. Update `transformation-understanding.md` so it reflects the latest best understanding of the work.

Prefer evidence over guesswork. If a detail is inferred rather than stated, mark it as an
assumption instead of presenting it as fact.

## What Good Discovery Captures

### Request Summary

State the problem in delivery terms:

- what is being transformed
- why the transformation exists
- what a successful outcome looks like

Avoid generic summaries. Name the systems, data shapes, files, processes, or business outputs
involved whenever the evidence supports it.

### Source Landscape

For each meaningful source, capture:

- system or file origin
- data or document type
- format and structure
- access method or dependency
- owner or responsible team if known
- quirks, gaps, and reliability concerns

### Target Landscape

For each target, capture:

- destination system, artifact, or interface
- expected format and delivery mode
- consumer or owner
- operational expectations such as cadence, triggers, or validation needs

### Constraints

Call out constraints that materially affect design or delivery, such as:

- data quality issues
- incomplete source coverage
- regulatory or audit requirements
- environment or access limitations
- sequencing or dependency constraints
- time, ownership, or authority boundaries

### Assumptions And Unknowns

Separate these clearly:

- assumptions are working beliefs that let planning continue
- missing critical information is anything that could change scope, approach, or risk materially

Ask clarifying questions only when the missing information is genuinely decision-shaping. Keep
those questions concise and grouped.

## Artifact Standards

When updating `transformation-understanding.md`:

- keep the template structure intact unless there is a strong reason to extend it
- replace placeholders with concrete content rather than adding loose notes around the template
- write in precise technical prose, not consultant filler
- prefer tables and tight bullets over long narrative blocks
- make the document readable by an engineer joining the session cold

The "Candidate Python-First Implementation Direction" should be a credible early direction, not
an overcommitted solution. It should explain the likely shape of a first implementation while
leaving room for later refinement.

## Decision Rules

- if evidence conflicts, note the conflict explicitly
- if a source is implied but not confirmed, label it as likely or assumed
- if the user intent mixes business goals and technical asks, translate both into implementation-facing language
- if discovery reveals downstream coupling, signal that dependency mapping should take over next

## Done When

This skill has done its job when:

- the request can be explained clearly in one pass
- the main sources and targets are identified
- the critical constraints and assumptions are visible
- the open questions are specific rather than vague
- another agent could start dependency analysis or delivery planning without re-reading every upload
