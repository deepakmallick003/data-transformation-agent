"""Deployment helpers and template rendering."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from config.settings import resolve_agent_name
from tools.s3_tools import resolve_s3_settings

DEFAULT_EXECUTION_ROLE_NAME = "AgentCoreRuntimeExecutionRole"

DEPLOY_OPTIONAL_ENV_KEYS = [
    "AGENT_TOOLS",
    "ATHENA_DATABASE",
    "ATHENA_OUTPUT_LOCATION",
    "KNOWLEDGE_BASE_ID",
    "KB_MAX_RESULTS",
    "S3_READ_BUCKET",
    "S3_READ_PREFIX",
    "S3_WRITE_BUCKET",
    "S3_MAX_LIST_RESULTS",
    "S3_MAX_OBJECT_BYTES",
]

DEPLOY_BUCKET_TAG_KEYS = [
    "AWS_TAG_CREATEDBY",
    "AWS_TAG_PURPOSE",
    "AWS_TAG_PROJECT",
    "AWS_TAG_ENVIRONMENT",
    "AWS_TAG_OWNER",
    "AWS_TAG_EXPIRYDATE",
]

DEPLOY_BUCKET_TAG_NAME_MAP = {
    "AWS_TAG_CREATEDBY": "CreatedBy",
    "AWS_TAG_PURPOSE": "Purpose",
    "AWS_TAG_PROJECT": "Project",
    "AWS_TAG_ENVIRONMENT": "Environment",
    "AWS_TAG_OWNER": "Owner",
    "AWS_TAG_EXPIRYDATE": "ExpiryDate",
}


def resolve_execution_role_name(
    default_name: str = DEFAULT_EXECUTION_ROLE_NAME,
) -> str:
    """Resolve the configured AgentCore execution role name."""
    return os.getenv("AGENTCORE_EXECUTION_ROLE_NAME", "").strip() or default_name


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def run(cmd: list[str], root: Path) -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    return subprocess.run(cmd, cwd=str(root), env=env).returncode


def run_capture(cmd: list[str], root: Path) -> str:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    result = subprocess.run(
        cmd,
        cwd=str(root),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def resolve_agentcore(root: Path) -> str:
    local = root / ".venv" / "bin" / "agentcore"
    if local.exists():
        return str(local)
    found = shutil.which("agentcore")
    if found:
        return found
    raise SystemExit("Could not find `agentcore`.")


def resolve_account_id(root: Path) -> str:
    account_id = os.getenv("AWS_ACCOUNT_ID", "").strip()
    if account_id:
        return account_id
    role_arn = os.getenv("AGENTCORE_EXECUTION_ROLE_ARN", "").strip()
    if role_arn:
        parts = role_arn.split(":")
        if len(parts) >= 5 and parts[4]:
            return parts[4]
    return run_capture(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
        root,
    )


def resolve_role_arn(account_id: str, role_name: str) -> str:
    explicit = os.getenv("AGENTCORE_EXECUTION_ROLE_ARN", "").strip()
    if explicit:
        return explicit
    return f"arn:aws:iam::{account_id}:role/{role_name}"


def resolve_platform() -> str:
    machine = platform.machine().lower()
    return "linux/arm64" if machine in {"arm64", "aarch64"} else "linux/amd64"


def resolve_codebuild_source_bucket(account_id: str, aws_region: str) -> str:
    return f"bedrock-agentcore-codebuild-sources-{account_id}-{aws_region}"


def resolve_memory_mode() -> str:
    mode = os.getenv("AGENTCORE_MEMORY_MODE", "STM_ONLY").strip().upper()
    valid_modes = {"NO_MEMORY", "STM_ONLY", "STM_AND_LTM"}
    if mode not in valid_modes:
        raise SystemExit(
            "AGENTCORE_MEMORY_MODE must be one of: " + ", ".join(sorted(valid_modes))
        )
    return mode


def normalize_bucket_region(location: str | None) -> str:
    if not location:
        return "us-east-1"
    if location == "EU":
        return "eu-west-1"
    return location


def deploy_bucket_tags() -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    missing: list[str] = []
    for key in DEPLOY_BUCKET_TAG_KEYS:
        value = os.getenv(key, "").strip()
        if not value:
            missing.append(key)
        else:
            tags.append({"Key": DEPLOY_BUCKET_TAG_NAME_MAP[key], "Value": value})
    if missing:
        raise SystemExit(
            "Missing required environment variables for deployment bucket tagging: "
            + ", ".join(missing)
        )
    return tags


def render_template(text: str, values: dict[str, str]) -> str:
    for key in sorted(values, key=len, reverse=True):
        text = text.replace(f"__{key}__", values[key])
    return text


def render_optional_env_block() -> str:
    lines: list[str] = []
    for key in DEPLOY_OPTIONAL_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'ENV {key}="{escaped}"')
    return "\n".join(lines)


def build_render_values(root: Path) -> dict[str, str]:
    agent_name = resolve_agent_name()
    role_name = resolve_execution_role_name()
    account_id = resolve_account_id(root)
    aws_region = require_env("AWS_REGION")
    s3_settings = resolve_s3_settings(
        agent_name=agent_name,
        default_read_bucket="YOUR_BUCKET_NAME",
    )
    return {
        "PYTHON_BASE_IMAGE": os.getenv(
            "AGENTCORE_PYTHON_BASE_IMAGE",
            "public.ecr.aws/docker/library/python:3.13-slim",
        ),
        "AWS_REGION": aws_region,
        "ANTHROPIC_MODEL": require_env("ANTHROPIC_MODEL"),
        "ANTHROPIC_SMALL_FAST_MODEL": require_env("ANTHROPIC_SMALL_FAST_MODEL"),
        "OPTIONAL_ENV_BLOCK": render_optional_env_block(),
        "AGENT_NAME": agent_name,
        "ENTRYPOINT": os.getenv("AGENTCORE_ENTRYPOINT", "main.py"),
        "PLATFORM": resolve_platform(),
        "EXECUTION_ROLE_ARN": resolve_role_arn(account_id, role_name),
        "AWS_ACCOUNT_ID": account_id,
        "CODEBUILD_SOURCE_BUCKET": resolve_codebuild_source_bucket(account_id, aws_region),
        "S3_READ_BUCKET": s3_settings.read_bucket,
        "S3_READ_PREFIX": s3_settings.read_prefix,
        "S3_READ_OBJECT_PATH": s3_settings.read_object_path,
        "S3_WRITE_BUCKET": s3_settings.write_bucket,
        "S3_WRITE_PREFIX": s3_settings.write_prefix,
        "S3_WRITE_OBJECT_PATH": s3_settings.write_object_path,
        "AGENTCORE_MEMORY_MODE": resolve_memory_mode(),
    }


def render_policy_template(
    template_path: Path,
    values: dict[str, str],
    optional_s3_write_block_template_path: Path | None = None,
) -> str:
    policy = json.loads(render_template(template_path.read_text(encoding="utf-8"), values))
    if optional_s3_write_block_template_path and values["S3_WRITE_BUCKET"]:
        extra_statements = json.loads(
            render_template(
                optional_s3_write_block_template_path.read_text(encoding="utf-8"),
                values,
            )
        )
        policy["Statement"].extend(extra_statements)
    return json.dumps(policy)
