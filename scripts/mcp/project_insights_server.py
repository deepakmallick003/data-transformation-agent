from __future__ import annotations

import os
import platform
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from mcp.server import FastMCP
from mcp.types import ToolAnnotations


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

PROJECT_ROOT = Path(
    os.environ.get("DATA_TRANSFORM_AGENT_PROJECT_ROOT", Path(__file__).resolve().parents[2])
).resolve()
SERVER = FastMCP("local_insights")


def _package_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "not installed"


def _parse_skill_frontmatter(skill_path: Path) -> tuple[str, str]:
    name = skill_path.parent.name
    description = ""
    lines = skill_path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                break
            if stripped.startswith("name:"):
                name = stripped.split(":", maxsplit=1)[1].strip()
            elif stripped.startswith("description:"):
                description = stripped.split(":", maxsplit=1)[1].strip()
    return name, description


@SERVER.tool(
    name="inspect_python_runtime",
    description="Inspect the Python runtime, executable, platform, and key package versions used by this project.",
    annotations=READ_ONLY,
)
def inspect_python_runtime() -> str:
    lines = [
        f"python_version: {platform.python_version()}",
        f"python_executable: {sys.executable}",
        f"platform: {platform.platform()}",
        f"claude-agent-sdk: {_package_version('claude-agent-sdk')}",
        f"mcp: {_package_version('mcp')}",
        f"fastapi: {_package_version('fastapi')}",
        f"flask: {_package_version('flask')}",
    ]
    return "\n".join(lines)


@SERVER.tool(
    name="list_skill_inventory",
    description="List project skills and plugin skills discovered in this repository, including their names and descriptions.",
    annotations=READ_ONLY,
)
def list_skill_inventory() -> str:
    skill_paths = sorted((PROJECT_ROOT / ".claude" / "skills").glob("*/SKILL.md"))
    plugin_skill_paths = sorted((PROJECT_ROOT / "claude-plugins").glob("*/skills/*/SKILL.md"))
    sections: list[str] = ["Project skills:"]

    if skill_paths:
        for path in skill_paths:
            name, description = _parse_skill_frontmatter(path)
            sections.append(f"- {name}: {description}")
    else:
        sections.append("- none found")

    sections.append("Plugin skills:")
    if plugin_skill_paths:
        for path in plugin_skill_paths:
            plugin_name = path.parents[2].name
            name, description = _parse_skill_frontmatter(path)
            sections.append(f"- {plugin_name}:{name}: {description}")
    else:
        sections.append("- none found")

    return "\n".join(sections)


@SERVER.tool(
    name="git_worktree_summary",
    description="Show a concise git worktree summary for the repository, including the repo root and current status when git metadata is available.",
    annotations=READ_ONLY,
)
def git_worktree_summary() -> str:
    root_result = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if root_result.returncode != 0:
        return "Git metadata is not available from this project root."

    status_result = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "status", "--short"],
        check=False,
        capture_output=True,
        text=True,
    )
    status_text = status_result.stdout.strip() or "clean working tree"
    return "\n".join(
        [
            f"repo_root: {root_result.stdout.strip()}",
            "status:",
            status_text,
        ]
    )


if __name__ == "__main__":
    SERVER.run()
