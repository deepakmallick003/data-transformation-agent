from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.session.manager import SessionManager
from app.session.templates import read_template
from app.transformation.models import CapabilityId


IMPLEMENTATION_GATED_CAPABILITIES: set[CapabilityId] = {
    "implementation_generation",
    "validation_and_reconciliation",
    "delivery_readiness",
    "approval_and_evidence",
}


@dataclass(frozen=True)
class SessionReadiness:
    source_clear: bool
    target_clear: bool
    understanding_updated: bool
    dependency_map_updated: bool
    delivery_plan_updated: bool

    @property
    def implementation_ready(self) -> bool:
        return self.source_clear and self.target_clear and self.understanding_updated


class TransformationGovernancePolicy:
    def __init__(self, session_manager: SessionManager, session_id: str) -> None:
        self.session_manager = session_manager
        self.session_id = session_id

    def allowed_direct_write_roots(self) -> list[Path]:
        return [self.session_manager.scratch_root(self.session_id)]

    def protected_session_roots(self) -> list[Path]:
        session_root = self.session_manager.session_root(self.session_id)
        return [
            session_root / "artifacts",
            session_root / "uploads",
            session_root / "outputs",
        ]

    def assess_readiness(self) -> SessionReadiness:
        understanding = self._artifact_content("transformation-understanding.md")
        dependency_map = self._artifact_content("data-dependency-map.md")
        delivery_plan = self._artifact_content("delivery-implementation-plan.md")
        return SessionReadiness(
            source_clear=self._has_non_placeholder_row(
                understanding,
                blank_row="|  |  |  |  |  |  |",
                required_heading="## Source Landscape",
            ),
            target_clear=self._has_non_placeholder_row(
                understanding,
                blank_row="|  |  |  |  |  |  |",
                required_heading="## Target Landscape",
            ),
            understanding_updated=self._artifact_updated_from_seed("transformation-understanding.md"),
            dependency_map_updated=dependency_map.strip()
            != self._template_content("data-dependency-map.md").strip(),
            delivery_plan_updated=delivery_plan.strip()
            != self._template_content("delivery-implementation-plan.md").strip(),
        )

    def capability_gate_reason(self, capabilities: list[CapabilityId]) -> str | None:
        if not any(capability in IMPLEMENTATION_GATED_CAPABILITIES for capability in capabilities):
            return None
        readiness = self.assess_readiness()
        if readiness.implementation_ready:
            return None
        return (
            "Implementation-oriented capability work requires source and target clarity in "
            "transformation-understanding.md before generating code, delivery packs, or approval evidence."
        )

    def output_write_gate_reason(self) -> str | None:
        readiness = self.assess_readiness()
        if readiness.implementation_ready:
            return None
        return (
            "Generated outputs are gated until the source and target are clarified in "
            "transformation-understanding.md."
        )

    def artifact_update_gate_reason(self, artifact_name: str, reason: str | None) -> str | None:
        if not reason or not reason.strip():
            return f"Artifact updates to {artifact_name} require a non-empty reason for auditability."
        return None

    def _artifact_updated_from_seed(self, artifact_name: str) -> bool:
        return self._artifact_content(artifact_name).strip() != self._template_content(artifact_name).strip()

    def _artifact_content(self, artifact_name: str) -> str:
        return self.session_manager.read_artifact(self.session_id, artifact_name)

    def _template_content(self, artifact_name: str) -> str:
        return read_template(self.session_manager.templates_root, artifact_name)

    def _has_non_placeholder_row(self, content: str, *, blank_row: str, required_heading: str) -> bool:
        if required_heading not in content:
            return False
        section = self._section_body(content, required_heading)
        table_lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
        if not table_lines:
            return False

        for line in table_lines:
            normalized = line.replace(" ", "")
            if normalized in {"|---|---|", "|---|---|---|", "|---|---|---|---|", "|---|---|---|---|---|", "|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|"}:
                continue
            if normalized == blank_row.replace(" ", ""):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if any(cell for cell in cells):
                return True
        return False

    def _section_body(self, content: str, heading: str) -> str:
        start = content.find(heading)
        if start == -1:
            return ""
        start = content.find("\n", start)
        if start == -1:
            return ""
        section = content[start + 1 :]
        next_heading = section.find("\n## ")
        if next_heading == -1:
            return section
        return section[:next_heading]
