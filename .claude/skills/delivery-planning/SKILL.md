---
name: delivery-planning
description: Turn transformation understanding and dependency analysis into a credible implementation plan, authority path, and execution package. Use when the work is moving from analysis into delivery and keep delivery-implementation-plan.md concrete and execution-ready.
---

# Delivery Planning

## Purpose

Use this skill to convert understanding into execution. The result should help a team decide
what to build first, what evidence is needed, who must sign off, and how delivery will be
validated and operated.

Keep `delivery-implementation-plan.md` current through the session MCP tools.

## Use This Skill When

- the transformation is understood well enough to plan implementation
- dependencies, risks, or authority checkpoints need to be turned into a practical sequence
- the team needs a first delivery package, not just analysis
- the user wants Python-first implementation thinking, phased delivery, or output design

Do not produce a polished but hollow plan. The point is operational readiness.

## Working Method

1. Start from the current discovery and dependency artifacts.
2. Decide the most credible first delivery slice.
3. Convert that into deliverables, implementation steps, validation approach, and authority inputs.
4. Update `delivery-implementation-plan.md` so it reads like a working execution plan.
5. Keep the plan honest about dependencies, unknowns, and sequencing risk.

## Planning Priorities

### Proposed Deliverables

Favor deliverables that materially move the work forward, such as:

- Python transformation code
- mapping specifications
- validation scripts
- sample outputs
- operational run guidance
- authority or sign-off packs

Do not list aspirational outputs unless they are likely to be produced.

### Implementation Plan

Sequence the work in a way that reduces risk early. Strong plans usually:

- validate source assumptions before heavy build work
- prove the core transformation on a narrow but representative slice
- add controls and reconciliation before scaling up
- separate mandatory delivery steps from later optimizations

Each step should name the input needed, the expected output, and anything blocking progress.

### Authority And Sign-Off Inputs

Surface who needs to approve what, including:

- business owners
- data owners
- platform or environment owners
- governance or compliance stakeholders
- operational support teams

Name the evidence required for each decision where possible.

### Deployment And Operations

Consider:

- runtime location
- scheduling or triggering
- failure handling
- observability
- rerun or rollback expectations
- support ownership

If operational details are not yet known, identify the decisions that still need to be made.

### Testing And Validation

The testing plan should reflect the actual transformation risk. Consider:

- representative input coverage
- golden samples
- reconciliations against source totals
- edge cases and malformed inputs
- contract checks for downstream consumers
- manual review or sign-off steps where automation is not enough

## Python-First Guidance

Prefer Python as the first implementation vehicle when the path is still emerging, especially for:

- document parsing
- file conversion
- data normalization
- rule execution
- validation and reconciliation
- producing intermediate artifacts for review

Leave space for later SQL, dbt, orchestration, or platform-native implementations when they are
clearly the next step, but do not prematurely optimize the first deliverable around them.

## Writing Standards

When updating `delivery-implementation-plan.md`:

- keep the template structure recognizable and useful
- write like a lead engineer preparing a handoff, not like a brainstorming note
- distinguish confirmed steps from contingent follow-ups
- make risks, blockers, and dependencies visible rather than implied
- keep deliverables tied to concrete outcomes and owners

## Decision Rules

- if there is not enough evidence for a full plan, produce a phased plan with explicit discovery gates
- if authority is missing, show exactly what decision is needed and what evidence would unlock it
- if multiple delivery options exist, recommend one and briefly justify it
- if the implementation should begin with a thin slice, say what that slice is and why

## Done When

This skill has done its job when:

- the next implementation steps are clear
- proposed deliverables are realistic
- sign-off and authority needs are visible
- testing and operational considerations are not afterthoughts
- the user could hand the artifact to an engineer or delivery lead and get meaningful execution started
