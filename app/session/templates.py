from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TemplateDefinition:
    source: str
    destination: str


TEMPLATE_DEFINITIONS = [
    TemplateDefinition(
        source="transformation-understanding-template.md",
        destination="transformation-understanding.md",
    ),
    TemplateDefinition(
        source="data-dependency-map-template.md",
        destination="data-dependency-map.md",
    ),
    TemplateDefinition(
        source="delivery-implementation-plan-template.md",
        destination="delivery-implementation-plan.md",
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
