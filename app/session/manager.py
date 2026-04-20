from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.models import (
    ArtifactInfo,
    ArtifactKind,
    DocumentSectionStatus,
    MessageRecord,
    MessageRole,
    RuntimeActivityEntry,
    RuntimeState,
    SessionDetail,
    SessionRecord,
    TransformationDocumentStatus,
    UserFacingStatus,
    WorkflowType,
)
from app.session.templates import TEMPLATE_DEFINITIONS, instantiate_session_templates, list_template_definitions


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
        self.sessions_root = sessions_root
        self.templates_root = templates_root
        self._messages: list[MessageRecord] = []
        self._statuses: list[UserFacingStatus] = []

        self.sessions_root.mkdir(parents=True, exist_ok=True)

        now = utc_now_iso()
        self._session = SessionRecord(
            id=uuid.uuid4().hex[:12],
            title="Active Runtime Session",
            notes="Runtime session stored under storage/sessions for inspection and downloads.",
            created_at=now,
            updated_at=now,
            sdk_session_id=None,
        )
        self._runtime_root = self.sessions_root / self._session.id
        self._activity_path = self._runtime_root / ".activity.jsonl"

        uploads_root = self._runtime_root / "uploads"
        artifacts_root = self._runtime_root / "artifacts"
        outputs_root = self._runtime_root / "outputs"
        workspace_root = self._runtime_root / "workspace"
        scratch_root = workspace_root / "scratch"
        for directory in (
            self._runtime_root,
            uploads_root,
            artifacts_root,
            outputs_root,
            workspace_root,
            scratch_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        instantiate_session_templates(self.templates_root, artifacts_root)
        self._write_session_metadata()
        self._write_messages()
        self.record_activity(
            event="runtime-started",
            title="Runtime session ready",
            detail=f"A fresh agent workspace was created at {self._runtime_root}.",
            level="success",
        )

    @property
    def audit_path(self) -> Path:
        return self._activity_path

    @property
    def active_session_id(self) -> str:
        return self._session.id

    def list_sessions(self) -> list[SessionRecord]:
        sessions: list[SessionRecord] = []
        for session_file in sorted(self.sessions_root.glob("*/session.json")):
            try:
                sessions.append(SessionRecord.model_validate_json(session_file.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001
                continue
        active_known = any(item.id == self._session.id for item in sessions)
        if not active_known:
            sessions.append(self._session)
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)

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
        self._write_session_metadata()
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
        self._write_messages()
        self.touch_session(session_id)

    def read_messages(self, session_id: str) -> list[MessageRecord]:
        self._ensure_active_session(session_id)
        return list(self._messages)

    def store_upload(self, session_id: str, filename: str, content: bytes) -> Path:
        self._ensure_active_session(session_id)
        safe_name = self._versioned_name(self.session_root(session_id) / "uploads", filename)
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
        self.append_message(
            session_id=session_id,
            role="system",
            content=f"Uploaded {safe_name}",
            metadata={
                "message_kind": "upload",
                "filename": safe_name,
                "path": str(destination.relative_to(self.session_root(session_id))),
                "download_path": f"/api/runtime/files/upload/{safe_name}",
            },
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
        safe_name = self._versioned_name(self.session_root(session_id) / "outputs", filename)
        if not safe_name:
            raise ValueError("Output filename cannot be empty.")
        destination = self.session_root(session_id) / "outputs" / safe_name
        destination.write_text(content, encoding="utf-8")
        self.touch_session(session_id)
        self.append_message(
            session_id=session_id,
            role="system",
            content=f"Generated output {safe_name}",
            metadata={
                "message_kind": "output",
                "filename": safe_name,
                "path": str(destination.relative_to(self.session_root(session_id))),
                "download_path": f"/api/runtime/files/output/{safe_name}",
            },
        )
        return destination

    def upsert_output(
        self,
        session_id: str,
        filename: str,
        content: str,
        *,
        description: str,
    ) -> Path:
        self._ensure_active_session(session_id)
        safe_name = Path(filename).name
        if not safe_name:
            raise ValueError("Output filename cannot be empty.")
        destination = self.session_root(session_id) / "outputs" / safe_name
        previous = destination.read_text(encoding="utf-8") if destination.exists() else None
        destination.write_text(content, encoding="utf-8")
        self.touch_session(session_id)
        if previous != content:
            self.append_message(
                session_id=session_id,
                role="system",
                content=f"Generated output {safe_name}",
                metadata={
                    "message_kind": "output",
                    "filename": safe_name,
                    "path": str(destination.relative_to(self.session_root(session_id))),
                    "download_path": f"/api/runtime/files/output/{safe_name}",
                },
            )
            self.record_activity(
                event="output-upserted",
                title=f"Updated derived output {safe_name}",
                detail=description,
                level="success",
                metadata={"filename": safe_name},
            )
        return destination

    def session_root(self, session_id: str) -> Path:
        self._ensure_active_session(session_id)
        return self._runtime_root

    def workspace_root(self, session_id: str) -> Path:
        return self.session_root(session_id) / "workspace"

    def scratch_root(self, session_id: str) -> Path:
        return self.workspace_root(session_id) / "scratch"

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

    def resolve_output_path(self, session_id: str, output_name: str) -> Path:
        self._ensure_active_session(session_id)
        safe_name = Path(output_name).name
        if not safe_name:
            raise FileNotFoundError("Output name cannot be empty.")
        target = self.session_root(session_id) / "outputs" / safe_name
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(target)
        return target

    def resolve_asset_path(self, session_id: str, kind: ArtifactKind, name: str) -> Path:
        if kind == "artifact":
            return self.resolve_artifact_path(session_id, name)
        if kind == "upload":
            return self.resolve_upload_path(session_id, name)
        return self.resolve_output_path(session_id, name)

    def set_statuses(self, statuses: list[UserFacingStatus]) -> None:
        self._statuses = [status.model_copy() for status in statuses]

    def get_statuses(self) -> list[UserFacingStatus]:
        return [status.model_copy() for status in self._statuses]

    def touch_session(self, session_id: str) -> None:
        self._ensure_active_session(session_id)
        self._session = self._session.model_copy(update={"updated_at": utc_now_iso()})
        self._write_session_metadata()

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
            statuses=self.get_statuses(),
            documents=self.document_statuses(self.active_session_id),
        )

    def _ensure_active_session(self, session_id: str) -> None:
        if session_id != self._session.id:
            raise FileNotFoundError(f"Session not found: {session_id}")

    def _write_session_metadata(self) -> None:
        self.metadata_path(self._session.id).write_text(
            self._session.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def _write_messages(self) -> None:
        lines = [
            message.model_dump_json()
            for message in self._messages
        ]
        content = "\n".join(lines)
        if content:
            content += "\n"
        self.messages_path(self._session.id).write_text(content, encoding="utf-8")

    def _versioned_name(self, directory: Path, filename: str) -> str:
        candidate = Path(filename).name or "file"
        stem = Path(candidate).stem
        suffix = Path(candidate).suffix
        version = 1
        current = candidate
        while (directory / current).exists():
            version += 1
            current = f"{stem}__v{version}{suffix}"
        return current

    def document_statuses(self, session_id: str) -> list[TransformationDocumentStatus]:
        self._ensure_active_session(session_id)
        statuses: list[TransformationDocumentStatus] = []
        for definition in TEMPLATE_DEFINITIONS:
            current = self.read_artifact(session_id, definition.destination)
            template = (self.templates_root / definition.source).read_text(encoding="utf-8")
            sections = self._document_sections(current, template)
            evidence_sections = sum(1 for item in sections if item.state == "complete")
            assumption_sections = sum(1 for item in sections if item.state == "assumption")
            gap_sections = sum(1 for item in sections if item.state == "gap")
            total = max(len(sections), 1)
            completion_ratio = round((evidence_sections + (0.5 * assumption_sections)) / total, 2)

            if evidence_sections == 0 and assumption_sections == 0:
                status = "not_started"
            elif gap_sections > 0:
                status = "needs_clarification" if assumption_sections or evidence_sections else "in_progress"
            else:
                status = "ready"

            statuses.append(
                TransformationDocumentStatus(
                    name=definition.destination,
                    title=definition.title,
                    description=definition.description,
                    status=status,
                    completion_ratio=completion_ratio,
                    evidence_sections=evidence_sections,
                    assumption_sections=assumption_sections,
                    gap_sections=gap_sections,
                    sections=sections,
                )
            )
        return statuses

    def build_merged_artifact_summary(self, session_id: str) -> str:
        self._ensure_active_session(session_id)
        lines = [
            "# Transformation Summary",
            "",
            "This merged markdown summary combines the current session artifacts in template order.",
            "",
        ]
        for definition in list_template_definitions():
            try:
                content = self.read_artifact(session_id, definition.destination).strip()
            except FileNotFoundError:
                continue
            if not content:
                continue
            lines.extend(["---", "", content, ""])
        return "\n".join(lines).strip() + "\n"

    def build_output_readme(self, session_id: str) -> str:
        self._ensure_active_session(session_id)
        outputs = [
            item
            for item in self.list_artifacts(session_id)
            if item.kind == "output"
        ]
        lines = [
            "# Transformation Output Guide",
            "",
            "This guide explains the generated outputs for the current transformation session and how to use them.",
            "",
            "## Output files",
            "",
        ]
        if outputs:
            lines.extend(
                f"- `{item.name}`"
                for item in outputs
                if item.name not in {"transformation_readme.md"}
            )
        else:
            lines.append("- No generated outputs are available yet.")

        lines.extend(
            [
                "",
                "## Recommended reading order",
                "",
                "- Start with `transformation_summary.md` to review the merged transformation context assembled from the governed session artifacts.",
                "- Review any mapping or validation markdown files to check rules, assumptions, and remaining gaps before using the outputs downstream.",
                "- If a Python implementation file is present, confirm the expected input filenames and paths before running it locally.",
                "- Use sample output or validation files, when present, to check whether the generated implementation aligns with the uploaded evidence and requested target.",
                "",
                "## Running generated Python",
                "",
                "- Run a generated Python script with `python <filename>` from the session output folder after confirming any required input files are available.",
                "- Review the script for placeholder paths, inferred assumptions, or expected schema names before production use.",
                "",
            ]
        )
        return "\n".join(lines)

    def _document_sections(
        self,
        current_content: str,
        template_content: str,
    ) -> list[DocumentSectionStatus]:
        headings = re.findall(r"^##\s+(.+)$", template_content, flags=re.MULTILINE)
        sections: list[DocumentSectionStatus] = []
        for heading in headings:
            current_section = self._section_body(current_content, heading)
            template_section = self._section_body(template_content, heading)
            normalized_current = self._normalize_section(current_section)
            normalized_template = self._normalize_section(template_section)

            if not normalized_current or normalized_current == normalized_template:
                state = "gap"
                detail = "Still mostly template or unresolved."
            else:
                lower = normalized_current.lower()
                if any(token in lower for token in ("assumption", "assumed", "infer", "likely", "probably")):
                    state = "assumption"
                    detail = "Contains working assumptions or inferred detail."
                elif any(token in lower for token in ("missing", "open question", "tbd", "to be determined", "unknown")):
                    state = "gap"
                    detail = "Still has open gaps or missing detail."
                else:
                    state = "complete"
                    detail = "Filled with concrete transformation detail."

            sections.append(
                DocumentSectionStatus(
                    title=heading,
                    state=state,
                    detail=detail,
                )
            )
        return sections

    def _section_body(self, content: str, heading: str) -> str:
        pattern = rf"^##\s+{re.escape(heading)}\s*$"
        match = re.search(pattern, content, flags=re.MULTILINE)
        if match is None:
            return ""
        start = match.end()
        next_match = re.search(r"^##\s+.+$", content[start:], flags=re.MULTILINE)
        if next_match is None:
            return content[start:]
        return content[start : start + next_match.start()]

    def _normalize_section(self, content: str) -> str:
        lines = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped in {"", "-", "|  |  |", "|  |  |  |", "|  |  |  |  |", "|  |  |  |  |  |", "|  |  |  |  |  |  |"}:
                continue
            lines.append(stripped)
        return "\n".join(lines).strip()
