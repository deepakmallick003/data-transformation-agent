from typing import Any, Literal

from pydantic import BaseModel, Field


WorkflowType = Literal[
    "general",
    "discovery",
    "dependency-mapping",
    "delivery-planning",
]
ProgressState = Literal["pending", "working", "blocked", "ready", "done"]

MessageRole = Literal["user", "assistant", "system"]
ArtifactKind = Literal["artifact", "upload", "output"]


class SessionCreateRequest(BaseModel):
    title: str | None = None
    notes: str = ""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    workflow: WorkflowType = "general"
    skills: list[str] = Field(default_factory=list)


class TaskRunRequest(BaseModel):
    objective: str = Field(min_length=1)
    workflow: WorkflowType = "general"


class ArtifactInfo(BaseModel):
    name: str
    kind: ArtifactKind
    path: str
    updated_at: str
    size_bytes: int


class MessageRecord(BaseModel):
    role: MessageRole
    content: str
    created_at: str
    workflow: WorkflowType | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionRecord(BaseModel):
    id: str
    title: str
    notes: str
    created_at: str
    updated_at: str
    sdk_session_id: str | None = None


class SessionDetail(BaseModel):
    session: SessionRecord
    messages: list[MessageRecord]
    artifacts: list[ArtifactInfo]


class RuntimeActivityEntry(BaseModel):
    created_at: str
    event: str
    title: str
    detail: str | None = None
    level: Literal["info", "success", "warning", "error"] = "info"
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserFacingStatus(BaseModel):
    id: str
    label: str
    state: ProgressState = "pending"
    detail: str | None = None


class DocumentSectionStatus(BaseModel):
    title: str
    state: Literal["complete", "assumption", "gap"] = "gap"
    detail: str | None = None


class TransformationDocumentStatus(BaseModel):
    name: str
    title: str
    description: str
    status: Literal["not_started", "in_progress", "needs_clarification", "ready"] = "not_started"
    completion_ratio: float = 0.0
    evidence_sections: int = 0
    assumption_sections: int = 0
    gap_sections: int = 0
    sections: list[DocumentSectionStatus] = Field(default_factory=list)


class RuntimeState(BaseModel):
    session: SessionRecord
    messages: list[MessageRecord]
    uploads: list[ArtifactInfo]
    outputs: list[ArtifactInfo]
    artifacts: list[ArtifactInfo]
    activity: list[RuntimeActivityEntry]
    statuses: list[UserFacingStatus] = Field(default_factory=list)
    documents: list[TransformationDocumentStatus] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session: SessionRecord
    reply: str
    workflow: WorkflowType
    artifacts: list[ArtifactInfo]
    uploads: list[ArtifactInfo]
    outputs: list[ArtifactInfo]
    activity: list[RuntimeActivityEntry]
    statuses: list[UserFacingStatus] = Field(default_factory=list)
    sdk_session_id: str | None = None
    raw_result: str | None = None
