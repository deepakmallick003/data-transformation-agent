from __future__ import annotations

import json
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.models import (
    ArtifactInfo,
    ArtifactKind,
    MessageRecord,
    MessageRole,
    RuntimeActivityEntry,
    RuntimeState,
    SessionDetail,
    SessionRecord,
    WorkflowType,
)
from app.session.templates import TEMPLATE_DEFINITIONS, instantiate_session_templates


ARTIFACT_DESTINATIONS = {item.destination for item in TEMPLATE_DEFINITIONS}
ASSET_LOCATIONS: tuple[tuple[ArtifactKind, str], ...] = (
    ("artifact", "artifacts"),
    ("upload", "uploads"),
    ("output", "outputs"),
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SessionManager:
    def __init__(self, sessions_root: Path, templates_root: Path) -> None:
        del sessions_root
        self.templates_root = templates_root
        self._temp_dir = tempfile.TemporaryDirectory(prefix="data-transformation-agent-")
        self._runtime_root = Path(self._temp_dir.name)
        self._activity_path = self._runtime_root / ".activity.jsonl"
        self._messages: list[MessageRecord] = []

        uploads_root = self._runtime_root / "uploads"
        artifacts_root = self._runtime_root / "artifacts"
        outputs_root = self._runtime_root / "outputs"
        for directory in (self._runtime_root, uploads_root, artifacts_root, outputs_root):
            directory.mkdir(parents=True, exist_ok=True)

        instantiate_session_templates(self.templates_root, artifacts_root)

        now = utc_now_iso()
        self._session = SessionRecord(
            id=uuid.uuid4().hex[:12],
            title="Active Runtime Session",
            notes="Ephemeral runtime session. State resets when the API process restarts.",
            created_at=now,
            updated_at=now,
            sdk_session_id=None,
        )
        self.record_activity(
            event="runtime-started",
            title="Ephemeral runtime session ready",
            detail="A fresh agent workspace was created for this process. Nothing persists across restarts.",
            level="success",
        )

    @property
    def audit_path(self) -> Path:
        return self._activity_path

    @property
    def active_session_id(self) -> str:
        return self._session.id

    def list_sessions(self) -> list[SessionRecord]:
        return [self._session]

    def create_session(self, title: str | None = None, notes: str = "") -> SessionRecord:
        del title, notes
        return self._session

    def get_session(self, session_id: str) -> SessionRecord:
        self._ensure_active_session(session_id)
        return self._session

    def set_sdk_session_id(self, session_id: str, sdk_session_id: str) -> SessionRecord:
        self._ensure_active_session(session_id)
        self._session = self._session.model_copy(
            update={"sdk_session_id": sdk_session_id, "updated_at": utc_now_iso()}
        )
        return self._session

    def append_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        workflow: WorkflowType | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._ensure_active_session(session_id)
        self._messages.append(
            MessageRecord(
                role=role,
                content=content,
                created_at=utc_now_iso(),
                workflow=workflow,
                metadata=metadata or {},
            )
        )
        self.touch_session(session_id)

    def read_messages(self, session_id: str) -> list[MessageRecord]:
        self._ensure_active_session(session_id)
        return list(self._messages)

    def store_upload(self, session_id: str, filename: str, content: bytes) -> Path:
        self._ensure_active_session(session_id)
        safe_name = Path(filename).name
        destination = self.session_root(session_id) / "uploads" / safe_name
        destination.write_bytes(content)
        self.touch_session(session_id)
        self.record_activity(
            event="upload-stored",
            title=f"Uploaded {safe_name}",
            detail=f"Stored in {destination.relative_to(self.session_root(session_id))}.",
            level="success",
            metadata={"filename": safe_name},
        )
        return destination

    def list_uploaded_files(self, session_id: str) -> list[str]:
        self._ensure_active_session(session_id)
        uploads_root = self.session_root(session_id) / "uploads"
        return sorted(
            str(path.relative_to(self.session_root(session_id)))
            for path in uploads_root.glob("*")
            if path.is_file()
        )

    def read_upload(self, session_id: str, upload_name: str) -> str:
        self._ensure_active_session(session_id)
        target = self.resolve_upload_path(session_id, upload_name)
        return target.read_text(encoding="utf-8", errors="replace")

    def list_artifacts(self, session_id: str) -> list[ArtifactInfo]:
        self._ensure_active_session(session_id)
        root = self.session_root(session_id)
        entries: list[ArtifactInfo] = []
        for kind, relative in ASSET_LOCATIONS:
            for path in sorted((root / relative).glob("*")):
                if not path.is_file():
                    continue
                stat = path.stat()
                entries.append(
                    ArtifactInfo(
                        name=path.name,
                        kind=kind,
                        path=str(path.relative_to(root)),
                        updated_at=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                        size_bytes=stat.st_size,
                    )
                )
        return sorted(entries, key=lambda item: item.updated_at, reverse=True)

    def read_artifact(self, session_id: str, artifact_name: str) -> str:
        self._ensure_active_session(session_id)
        target = self.resolve_artifact_path(session_id, artifact_name)
        return target.read_text(encoding="utf-8")

    def write_artifact(self, session_id: str, artifact_name: str, content: str) -> Path:
        self._ensure_active_session(session_id)
        target = self.resolve_artifact_path(session_id, artifact_name)
        target.write_text(content, encoding="utf-8")
        self.touch_session(session_id)
        return target

    def write_output(self, session_id: str, filename: str, content: str) -> Path:
        self._ensure_active_session(session_id)
        safe_name = Path(filename).name
        if not safe_name:
            raise ValueError("Output filename cannot be empty.")
        destination = self.session_root(session_id) / "outputs" / safe_name
        destination.write_text(content, encoding="utf-8")
        self.touch_session(session_id)
        return destination

    def session_root(self, session_id: str) -> Path:
        self._ensure_active_session(session_id)
        return self._runtime_root

    def metadata_path(self, session_id: str) -> Path:
        self._ensure_active_session(session_id)
        return self.session_root(session_id) / "session.json"

    def messages_path(self, session_id: str) -> Path:
        self._ensure_active_session(session_id)
        return self.session_root(session_id) / "messages.jsonl"

    def resolve_artifact_path(self, session_id: str, artifact_name: str) -> Path:
        self._ensure_active_session(session_id)
        safe_name = Path(artifact_name).name
        if safe_name not in ARTIFACT_DESTINATIONS:
            raise FileNotFoundError(f"Unsupported artifact name: {artifact_name}")
        return self.session_root(session_id) / "artifacts" / safe_name

    def resolve_upload_path(self, session_id: str, upload_name: str) -> Path:
        self._ensure_active_session(session_id)
        safe_name = Path(upload_name).name
        if not safe_name:
            raise FileNotFoundError("Upload name cannot be empty.")
        target = self.session_root(session_id) / "uploads" / safe_name
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(target)
        return target

    def touch_session(self, session_id: str) -> None:
        self._ensure_active_session(session_id)
        self._session = self._session.model_copy(update={"updated_at": utc_now_iso()})

    def record_activity(
        self,
        *,
        event: str,
        title: str,
        detail: str | None = None,
        level: str = "info",
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeActivityEntry:
        entry = RuntimeActivityEntry(
            created_at=utc_now_iso(),
            event=event,
            title=title,
            detail=detail,
            level=level,
            metadata=metadata or {},
        )
        with self._activity_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.model_dump(mode="json")) + "\n")
        return entry

    def list_activity(self) -> list[RuntimeActivityEntry]:
        if not self._activity_path.exists():
            return []
        entries: list[RuntimeActivityEntry] = []
        for line in self._activity_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(RuntimeActivityEntry.model_validate_json(line))
        return entries

    def get_session_detail(self, session_id: str) -> SessionDetail:
        self._ensure_active_session(session_id)
        return SessionDetail(
            session=self._session,
            messages=self.read_messages(session_id),
            artifacts=self.list_artifacts(session_id),
        )

    def get_runtime_state(self) -> RuntimeState:
        assets = self.list_artifacts(self.active_session_id)
        return RuntimeState(
            session=self._session,
            messages=list(self._messages),
            uploads=[item for item in assets if item.kind == "upload"],
            outputs=[item for item in assets if item.kind == "output"],
            artifacts=[item for item in assets if item.kind == "artifact"],
            activity=self.list_activity(),
        )

    def _ensure_active_session(self, session_id: str) -> None:
        if session_id != self._session.id:
            raise FileNotFoundError(f"Session not found: {session_id}")
