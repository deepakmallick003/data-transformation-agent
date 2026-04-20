from __future__ import annotations

from mcp.server import FastMCP
from mcp.types import ToolAnnotations

from app.core.config import get_settings
from app.core.models import ChatResponse
from app.runtime.agent import ClaudeTransformationAgent
from app.session.manager import SessionManager
from app.transformation.capabilities import get_capability
from app.transformation.models import (
    CapabilityId,
    StructuredTransformationContext,
    StructuredTransformationRequest,
)
from app.transformation.service import TransformationCapabilityService


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

MUTATING = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)

SETTINGS = get_settings()
SESSION_MANAGER = SessionManager(
    sessions_root=SETTINGS.sessions_root,
    templates_root=SETTINGS.templates_root,
)
CAPABILITY_SERVICE = TransformationCapabilityService()
AGENT = ClaudeTransformationAgent(
    settings=SETTINGS,
    session_manager=SESSION_MANAGER,
    capability_service=CAPABILITY_SERVICE,
)
SERVER = FastMCP("transformation_domain")


def _response_summary(response: ChatResponse) -> str:
    artifact_lines = [f"- {item.path}" for item in response.artifacts] or ["- none"]
    output_lines = [f"- {item.path}" for item in response.outputs] or ["- none"]
    return "\n".join(
        [
            f"session_id: {response.session.id}",
            "artifacts:",
            *artifact_lines,
            "outputs:",
            *output_lines,
            "",
            response.reply,
        ]
    )


async def _run_capability(
    capability_id: CapabilityId,
    *,
    objective: str,
    source_summary: str = "",
    target_summary: str = "",
    constraints: list[str] | None = None,
    notes: str = "",
    desired_outputs: list[str] | None = None,
) -> str:
    request = StructuredTransformationRequest(
        objective=objective,
        workflow=get_capability(capability_id).workflow,
        context=StructuredTransformationContext(
            source_summary=source_summary,
            target_summary=target_summary,
            constraints=constraints or [],
            notes=notes,
            desired_outputs=desired_outputs or [],
        ),
    )
    plan = CAPABILITY_SERVICE.plan_structured_request(
        request,
        capability_override=capability_id,
        surface="mcp",
    )
    response = await AGENT.run_execution_plan(
        session_id=SESSION_MANAGER.active_session_id,
        plan=plan,
    )
    return _response_summary(response)


@SERVER.tool(
    name="describe_transformation_capabilities",
    description="Describe the reusable transformation capabilities, their default workflows, and their governed artifact targets.",
    annotations=READ_ONLY,
)
def describe_transformation_capabilities() -> str:
    lines = []
    for capability in CAPABILITY_SERVICE.list_capabilities():
        lines.append(
            f"- {capability.id}: workflow={capability.workflow}; skill={capability.default_skill}; artifacts={', '.join(capability.artifacts)}"
        )
        lines.append(f"  {capability.description}")
    return "\n".join(lines)


@SERVER.tool(
    name="analyse_source",
    description="Run the reusable source analysis capability for transformation work.",
    annotations=MUTATING,
)
async def analyse_source(
    objective: str,
    source_summary: str = "",
    target_summary: str = "",
    constraints: list[str] | None = None,
    notes: str = "",
) -> str:
    return await _run_capability(
        "source_analysis",
        objective=objective,
        source_summary=source_summary,
        target_summary=target_summary,
        constraints=constraints,
        notes=notes,
    )


@SERVER.tool(
    name="interpret_target_contract",
    description="Run the reusable target contract analysis capability for transformation work.",
    annotations=MUTATING,
)
async def interpret_target_contract(
    objective: str,
    source_summary: str = "",
    target_summary: str = "",
    constraints: list[str] | None = None,
    notes: str = "",
) -> str:
    return await _run_capability(
        "target_contract_analysis",
        objective=objective,
        source_summary=source_summary,
        target_summary=target_summary,
        constraints=constraints,
        notes=notes,
    )


@SERVER.tool(
    name="generate_mapping_rules",
    description="Run the reusable mapping and rules capability for transformation work.",
    annotations=MUTATING,
)
async def generate_mapping_rules(
    objective: str,
    source_summary: str = "",
    target_summary: str = "",
    constraints: list[str] | None = None,
    notes: str = "",
) -> str:
    return await _run_capability(
        "mapping_and_rules",
        objective=objective,
        source_summary=source_summary,
        target_summary=target_summary,
        constraints=constraints,
        notes=notes,
    )


@SERVER.tool(
    name="generate_transform_code",
    description="Run the reusable implementation generation capability for transformation work.",
    annotations=MUTATING,
)
async def generate_transform_code(
    objective: str,
    source_summary: str = "",
    target_summary: str = "",
    constraints: list[str] | None = None,
    notes: str = "",
    desired_outputs: list[str] | None = None,
) -> str:
    return await _run_capability(
        "implementation_generation",
        objective=objective,
        source_summary=source_summary,
        target_summary=target_summary,
        constraints=constraints,
        notes=notes,
        desired_outputs=desired_outputs,
    )


@SERVER.tool(
    name="generate_validation_plan",
    description="Run the reusable validation and reconciliation capability for transformation work.",
    annotations=MUTATING,
)
async def generate_validation_plan(
    objective: str,
    source_summary: str = "",
    target_summary: str = "",
    constraints: list[str] | None = None,
    notes: str = "",
) -> str:
    return await _run_capability(
        "validation_and_reconciliation",
        objective=objective,
        source_summary=source_summary,
        target_summary=target_summary,
        constraints=constraints,
        notes=notes,
    )


@SERVER.tool(
    name="prepare_delivery_pack",
    description="Run the reusable delivery readiness capability for transformation work.",
    annotations=MUTATING,
)
async def prepare_delivery_pack(
    objective: str,
    source_summary: str = "",
    target_summary: str = "",
    constraints: list[str] | None = None,
    notes: str = "",
    desired_outputs: list[str] | None = None,
) -> str:
    return await _run_capability(
        "delivery_readiness",
        objective=objective,
        source_summary=source_summary,
        target_summary=target_summary,
        constraints=constraints,
        notes=notes,
        desired_outputs=desired_outputs,
    )


@SERVER.tool(
    name="assess_approval_requirements",
    description="Run the reusable approval and evidence capability for transformation work.",
    annotations=MUTATING,
)
async def assess_approval_requirements(
    objective: str,
    source_summary: str = "",
    target_summary: str = "",
    constraints: list[str] | None = None,
    notes: str = "",
) -> str:
    return await _run_capability(
        "approval_and_evidence",
        objective=objective,
        source_summary=source_summary,
        target_summary=target_summary,
        constraints=constraints,
        notes=notes,
    )


if __name__ == "__main__":
    SERVER.run()
