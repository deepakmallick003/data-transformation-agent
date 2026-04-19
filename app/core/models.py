from typing import Any, Literal

from pydantic import BaseModel, Field


WorkflowType = Literal[
    "general",
    "discovery",
    "dependency-mapping",
    "delivery-planning",
]

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


class RuntimeState(BaseModel):
    session: SessionRecord
    messages: list[MessageRecord]
    uploads: list[ArtifactInfo]
    outputs: list[ArtifactInfo]
    artifacts: list[ArtifactInfo]
    activity: list[RuntimeActivityEntry]


class ChatResponse(BaseModel):
    session: SessionRecord
    reply: str
    workflow: WorkflowType
    artifacts: list[ArtifactInfo]
    uploads: list[ArtifactInfo]
    outputs: list[ArtifactInfo]
    activity: list[RuntimeActivityEntry]
    sdk_session_id: str | None = None
    raw_result: str | None = None
