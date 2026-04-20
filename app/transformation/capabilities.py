from __future__ import annotations

from dataclasses import dataclass

from app.core.models import WorkflowType
from app.transformation.models import CapabilityId, CapabilitySurface, RuntimeAbilitySurface


@dataclass(frozen=True)
class TransformationCapabilityDefinition:
    id: CapabilityId
    label: str
    description: str
    workflow: WorkflowType
    default_skill: str
    user_status_label: str
    artifacts: tuple[str, ...] = ()
    user_visible: bool = False
    legacy_skill_aliases: tuple[str, ...] = ()


CAPABILITY_DEFINITIONS: tuple[TransformationCapabilityDefinition, ...] = (
    TransformationCapabilityDefinition(
        id="source_analysis",
        label="Source Analysis",
        description="Analyse source material, uploaded evidence, and operational context to establish the real transformation starting point.",
        workflow="discovery",
        default_skill="source-analysis",
        user_status_label="Understanding source",
        artifacts=("transformation-understanding.md",),
        user_visible=True,
        legacy_skill_aliases=("source_analysis", "transformation-discovery"),
    ),
    TransformationCapabilityDefinition(
        id="target_contract_analysis",
        label="Target Contract Analysis",
        description="Interpret target consumers, target contracts, delivery modes, and acceptance criteria before implementation decisions harden.",
        workflow="discovery",
        default_skill="target-contract-analysis",
        user_status_label="Interpreting target requirements",
        artifacts=("transformation-understanding.md",),
        legacy_skill_aliases=("target_contract_analysis",),
    ),
    TransformationCapabilityDefinition(
        id="mapping_and_rules",
        label="Mapping And Rules",
        description="Generate field mapping logic, rule sets, normalization steps, and transformation intent independent of specific document templates.",
        workflow="dependency-mapping",
        default_skill="mapping-and-rules",
        user_status_label="Mapping fields and rules",
        artifacts=("transformation-understanding.md", "data-dependency-map.md"),
        legacy_skill_aliases=("mapping_and_rules",),
    ),
    TransformationCapabilityDefinition(
        id="dependency_and_lineage",
        label="Dependency And Lineage",
        description="Trace upstream dependencies, lineage, joins, sequencing, controls, and downstream consumers for the transformation path.",
        workflow="dependency-mapping",
        default_skill="dependency-and-lineage",
        user_status_label="Tracing dependencies and lineage",
        artifacts=("data-dependency-map.md",),
        user_visible=True,
        legacy_skill_aliases=("dependency_and_lineage", "dependency-mapping"),
    ),
    TransformationCapabilityDefinition(
        id="implementation_generation",
        label="Implementation Generation",
        description="Shape implementation-ready transformation logic, starter code, and execution slices from the analysed source and target contract.",
        workflow="delivery-planning",
        default_skill="implementation-generation",
        user_status_label="Generating implementation",
        artifacts=("delivery-implementation-plan.md",),
        legacy_skill_aliases=("implementation_generation",),
    ),
    TransformationCapabilityDefinition(
        id="validation_and_reconciliation",
        label="Validation And Reconciliation",
        description="Define validation controls, reconciliation approach, failure handling, and proof points for the generated transformation.",
        workflow="delivery-planning",
        default_skill="validation-and-reconciliation",
        user_status_label="Checking validation needs",
        artifacts=("data-dependency-map.md", "delivery-implementation-plan.md"),
        legacy_skill_aliases=("validation_and_reconciliation",),
    ),
    TransformationCapabilityDefinition(
        id="delivery_readiness",
        label="Delivery Readiness",
        description="Prepare execution sequencing, deployment readiness, operational expectations, and delivery packaging for the transformation work.",
        workflow="delivery-planning",
        default_skill="delivery-readiness",
        user_status_label="Preparing outputs",
        artifacts=("delivery-implementation-plan.md",),
        user_visible=True,
        legacy_skill_aliases=("delivery_readiness", "delivery-planning"),
    ),
    TransformationCapabilityDefinition(
        id="approval_and_evidence",
        label="Approval And Evidence",
        description="Assess approval requirements, sign-off evidence, governance gaps, and audit-ready delivery evidence for the transformation.",
        workflow="delivery-planning",
        default_skill="transformation-delivery-helper:approval-and-evidence",
        user_status_label="Ready for review",
        artifacts=("delivery-implementation-plan.md",),
        user_visible=True,
        legacy_skill_aliases=(
            "transformation-delivery-helper:approval_and_evidence",
            "approval_and_evidence",
            "transformation-delivery-helper:authority-check",
            "authority-check",
        ),
    ),
)

CAPABILITY_INDEX = {item.id: item for item in CAPABILITY_DEFINITIONS}
LEGACY_SKILL_ALIASES = {
    alias: item.default_skill
    for item in CAPABILITY_DEFINITIONS
    for alias in item.legacy_skill_aliases
}

WORKFLOW_CAPABILITY_MAP: dict[WorkflowType, tuple[CapabilityId, ...]] = {
    "general": tuple(item.id for item in CAPABILITY_DEFINITIONS),
    "discovery": ("source_analysis", "target_contract_analysis"),
    "dependency-mapping": ("mapping_and_rules", "dependency_and_lineage"),
    "delivery-planning": (
        "implementation_generation",
        "validation_and_reconciliation",
        "delivery_readiness",
        "approval_and_evidence",
    ),
}

ABILITY_DEFINITIONS: tuple[RuntimeAbilitySurface, ...] = (
    RuntimeAbilitySurface(
        slash="/agent",
        label="Transformation Agent",
        workflow="general",
        capabilities=list(WORKFLOW_CAPABILITY_MAP["general"]),
        skills=[],
        description="Run the primary transformation agent. It chooses the right internal capabilities automatically.",
        primary=True,
        advanced=False,
    ),
    RuntimeAbilitySurface(
        slash="/discover",
        label="Discovery Lens",
        workflow="discovery",
        capabilities=list(WORKFLOW_CAPABILITY_MAP["discovery"]),
        skills=[],
        description="Optional focused view for source analysis and target contract clarification.",
        primary=False,
        advanced=True,
    ),
    RuntimeAbilitySurface(
        slash="/map",
        label="Dependency Lens",
        workflow="dependency-mapping",
        capabilities=list(WORKFLOW_CAPABILITY_MAP["dependency-mapping"]),
        skills=[],
        description="Optional focused view for lineage, dependency mapping, and rule generation.",
        primary=False,
        advanced=True,
    ),
    RuntimeAbilitySurface(
        slash="/plan",
        label="Delivery Lens",
        workflow="delivery-planning",
        capabilities=list(WORKFLOW_CAPABILITY_MAP["delivery-planning"]),
        skills=[],
        description="Optional focused view for implementation, validation, readiness, and evidence planning.",
        primary=False,
        advanced=True,
    ),
)


def list_capability_surfaces() -> list[CapabilitySurface]:
    return [
        CapabilitySurface(
            id=item.id,
            label=item.label,
            description=item.description,
            workflow=item.workflow,
            default_skill=item.default_skill,
            artifacts=list(item.artifacts),
            user_visible=item.user_visible,
            legacy_skill_aliases=list(item.legacy_skill_aliases),
        )
        for item in CAPABILITY_DEFINITIONS
    ]


def list_runtime_abilities() -> list[RuntimeAbilitySurface]:
    abilities: list[RuntimeAbilitySurface] = []
    for item in ABILITY_DEFINITIONS:
        abilities.append(
            item.model_copy(
                update={"skills": default_skills_for_capabilities(item.capabilities)}
            )
        )
    return abilities


def get_capability(capability_id: CapabilityId) -> TransformationCapabilityDefinition:
    return CAPABILITY_INDEX[capability_id]


def user_status_label_for_capability(capability_id: CapabilityId) -> str:
    return get_capability(capability_id).user_status_label


def normalize_skill_names(skills: list[str] | None) -> list[str]:
    if not skills:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        canonical = LEGACY_SKILL_ALIASES.get(skill, skill)
        if canonical not in seen:
            normalized.append(canonical)
            seen.add(canonical)
    return normalized


def capabilities_for_workflow(workflow: WorkflowType) -> list[CapabilityId]:
    return list(WORKFLOW_CAPABILITY_MAP[workflow])


def capability_ids_for_skills(skills: list[str]) -> list[CapabilityId]:
    normalized = set(normalize_skill_names(skills))
    resolved: list[CapabilityId] = []
    for definition in CAPABILITY_DEFINITIONS:
        if definition.default_skill in normalized:
            resolved.append(definition.id)
    return resolved


def default_skills_for_capabilities(capabilities: list[CapabilityId]) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for capability in capabilities:
        skill = get_capability(capability).default_skill
        if skill not in seen:
            resolved.append(skill)
            seen.add(skill)
    return resolved


def artifact_targets_for_capabilities(capabilities: list[CapabilityId]) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for capability in capabilities:
        for artifact_name in get_capability(capability).artifacts:
            if artifact_name not in seen:
                targets.append(artifact_name)
                seen.add(artifact_name)
    return targets
