from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.transformation.models import CapabilityId


@dataclass(frozen=True)
class TemplateDefinition:
    source: str
    destination: str
    title: str
    description: str
    capabilities: tuple[CapabilityId, ...]


TEMPLATE_DEFINITIONS = [
    TemplateDefinition(
        source="transformation-understanding-template.md",
        destination="transformation-understanding.md",
        title="Transformation Understanding",
        description="Session artifact that captures source analysis, target contract understanding, and early mapping intent.",
        capabilities=("source_analysis", "target_contract_analysis", "mapping_and_rules"),
    ),
    TemplateDefinition(
        source="data-dependency-map-template.md",
        destination="data-dependency-map.md",
        title="Data Dependency Map",
        description="Session artifact that captures lineage, dependencies, controls, and reconciliation points.",
        capabilities=("mapping_and_rules", "dependency_and_lineage", "validation_and_reconciliation"),
    ),
    TemplateDefinition(
        source="delivery-implementation-plan-template.md",
        destination="delivery-implementation-plan.md",
        title="Delivery And Implementation Plan",
        description="Session artifact that captures implementation generation, delivery readiness, approvals, and evidence.",
        capabilities=(
            "implementation_generation",
            "validation_and_reconciliation",
            "delivery_readiness",
            "approval_and_evidence",
        ),
    ),
]


def list_template_definitions() -> list[TemplateDefinition]:
    return list(TEMPLATE_DEFINITIONS)


def read_template(templates_root: Path, template_name: str) -> str:
    for definition in TEMPLATE_DEFINITIONS:
        if definition.destination == template_name or definition.source == template_name:
            return (templates_root / definition.source).read_text(encoding="utf-8")
    raise FileNotFoundError(f"Unsupported template name: {template_name}")


def instantiate_session_templates(templates_root: Path, artifacts_root: Path) -> list[Path]:
    artifacts_root.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for definition in TEMPLATE_DEFINITIONS:
        source_path = templates_root / definition.source
        destination_path = artifacts_root / definition.destination
        destination_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(destination_path)
    return created


def list_template_sections(templates_root: Path, template_name: str) -> list[str]:
    content = read_template(templates_root, template_name)
    return re.findall(r"^##\s+(.+)$", content, flags=re.MULTILINE)
