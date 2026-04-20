from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.models import ProgressState, WorkflowType


CapabilityId = Literal[
    "source_analysis",
    "target_contract_analysis",
    "mapping_and_rules",
    "dependency_and_lineage",
    "implementation_generation",
    "validation_and_reconciliation",
    "delivery_readiness",
    "approval_and_evidence",
]

ExposureSurface = Literal["chat", "api", "mcp"]


class StructuredTransformationContext(BaseModel):
    source_summary: str = ""
    target_summary: str = ""
    constraints: list[str] = Field(default_factory=list)
    notes: str = ""
    desired_outputs: list[str] = Field(default_factory=list)
    uploads: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructuredTransformationRequest(BaseModel):
    objective: str = Field(min_length=1)
    workflow: WorkflowType = "general"
    capabilities: list[CapabilityId] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    session_id: str | None = None
    context: StructuredTransformationContext = Field(default_factory=StructuredTransformationContext)


class TransformationExecutionPlan(BaseModel):
    objective: str = Field(min_length=1)
    workflow: WorkflowType
    capabilities: list[CapabilityId]
    skills: list[str]
    artifact_targets: list[str] = Field(default_factory=list)
    surface: ExposureSurface = "chat"
    mode: Literal["chat", "structured"] = "chat"
    context: StructuredTransformationContext = Field(default_factory=StructuredTransformationContext)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeAbilitySurface(BaseModel):
    slash: str
    label: str
    workflow: WorkflowType
    capabilities: list[CapabilityId] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    description: str
    primary: bool = False
    advanced: bool = False


class CapabilitySurface(BaseModel):
    id: CapabilityId
    label: str
    description: str
    workflow: WorkflowType
    default_skill: str
    artifacts: list[str] = Field(default_factory=list)
    user_visible: bool = False
    legacy_skill_aliases: list[str] = Field(default_factory=list)


class StructuredTransformationResponse(BaseModel):
    capability: CapabilityId | None = None
    capabilities: list[CapabilityId] = Field(default_factory=list)
    workflow: WorkflowType
    skills: list[str] = Field(default_factory=list)
    prompt_objective: str
    reply: str
    raw_result: str | None = None
    session_id: str
    artifacts: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class RuntimeStatusSummary(BaseModel):
    id: str
    label: str
    state: ProgressState = "pending"
    detail: str | None = None
