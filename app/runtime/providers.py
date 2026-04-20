from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from app.core.config import Settings


ClaudeProviderMode = Literal["anthropic", "bedrock", "mantle", "vertex", "foundry"]


@dataclass(frozen=True)
class ClaudeProviderConfig:
    mode: ClaudeProviderMode
    label: str
    env: dict[str, str]
    status: dict[str, str]


def resolve_claude_provider(settings: Settings) -> ClaudeProviderConfig:
    mode = _determine_provider_mode(settings)

    env = _baseline_env(settings)
    status = {"mode": mode}

    if mode == "bedrock":
        env["CLAUDE_CODE_USE_BEDROCK"] = "1"
        status["credential_mode"] = "aws"
        if settings.aws_region:
            env["AWS_REGION"] = settings.aws_region
        if settings.bedrock_base_url:
            env["ANTHROPIC_BEDROCK_BASE_URL"] = settings.bedrock_base_url
        if settings.bedrock_bearer_token:
            env["AWS_BEARER_TOKEN_BEDROCK"] = settings.bedrock_bearer_token
        label = "Amazon Bedrock"
    elif mode == "mantle":
        env["CLAUDE_CODE_USE_MANTLE"] = "1"
        if settings.enable_bedrock_invoke_api:
            env["CLAUDE_CODE_USE_BEDROCK"] = "1"
        status["credential_mode"] = "aws"
        if settings.aws_region:
            env["AWS_REGION"] = settings.aws_region
        if settings.bedrock_mantle_base_url:
            env["ANTHROPIC_BEDROCK_MANTLE_BASE_URL"] = settings.bedrock_mantle_base_url
        label = "Amazon Bedrock Mantle"
    elif mode == "vertex":
        env["CLAUDE_CODE_USE_VERTEX"] = "1"
        status["credential_mode"] = "gcp"
        if settings.vertex_project_id:
            env["ANTHROPIC_VERTEX_PROJECT_ID"] = settings.vertex_project_id
        if settings.vertex_base_url:
            env["ANTHROPIC_VERTEX_BASE_URL"] = settings.vertex_base_url
        if settings.cloud_ml_region:
            env["CLOUD_ML_REGION"] = settings.cloud_ml_region
        label = "Google Vertex AI"
    elif mode == "foundry":
        env["CLAUDE_CODE_USE_FOUNDRY"] = "1"
        status["credential_mode"] = "azure"
        if settings.foundry_resource:
            env["ANTHROPIC_FOUNDRY_RESOURCE"] = settings.foundry_resource
        if settings.foundry_base_url:
            env["ANTHROPIC_FOUNDRY_BASE_URL"] = settings.foundry_base_url
        if settings.foundry_api_key:
            env["ANTHROPIC_FOUNDRY_API_KEY"] = settings.foundry_api_key
        label = "Microsoft Foundry"
    else:
        status["credential_mode"] = "anthropic"
        label = "Anthropic API"

    if settings.claude_model:
        env["ANTHROPIC_MODEL"] = settings.claude_model
        status["model"] = settings.claude_model
    if settings.claude_default_sonnet_model:
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = settings.claude_default_sonnet_model
    if settings.claude_default_opus_model:
        env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = settings.claude_default_opus_model
    if settings.claude_default_haiku_model:
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = settings.claude_default_haiku_model
    if settings.claude_base_url and mode == "anthropic":
        env["ANTHROPIC_BASE_URL"] = settings.claude_base_url
    if settings.scrub_provider_credentials_in_subprocesses:
        env["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] = "1"

    return ClaudeProviderConfig(mode=mode, label=label, env=env, status=status)


def _baseline_env(settings: Settings) -> dict[str, str]:
    env: dict[str, str] = {}
    passthrough_keys = [
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_BEARER_TOKEN_BEDROCK",
        "ANTHROPIC_BEDROCK_BASE_URL",
        "ANTHROPIC_BEDROCK_MANTLE_BASE_URL",
        "ANTHROPIC_VERTEX_PROJECT_ID",
        "ANTHROPIC_VERTEX_BASE_URL",
        "CLOUD_ML_REGION",
        "GCLOUD_PROJECT",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "ANTHROPIC_FOUNDRY_RESOURCE",
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "ANTHROPIC_FOUNDRY_API_KEY",
        "AZURE_CLIENT_ID",
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_SECRET",
    ]
    for key in passthrough_keys:
        value = os.environ.get(key, "").strip()
        if value:
            env[key] = value
    env["ENABLE_TOOL_SEARCH"] = "auto:5"
    env["CLAUDE_CONFIG_DIR"] = str(settings.storage_root / ".claude-runtime")
    return env


def _determine_provider_mode(settings: Settings) -> ClaudeProviderMode:
    explicit = settings.claude_provider_mode
    if explicit != "auto":
        return explicit
    if settings.use_bedrock_mantle or os.environ.get("CLAUDE_CODE_USE_MANTLE") == "1":
        return "mantle"
    if settings.aws_region or os.environ.get("CLAUDE_CODE_USE_BEDROCK") == "1":
        return "bedrock"
    if settings.vertex_project_id or os.environ.get("CLAUDE_CODE_USE_VERTEX") == "1":
        return "vertex"
    if settings.foundry_resource or settings.foundry_base_url or os.environ.get("CLAUDE_CODE_USE_FOUNDRY") == "1":
        return "foundry"
    return "anthropic"
