import os
import shlex
import shutil
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, validation_alias=AliasChoices("API_PORT", "PORT"))
    ui_host: str = "127.0.0.1"
    ui_port: int = 5001
    backend_url: str | None = None
    auth_username: str = "admin"
    auth_password: str = "change-me"
    auth_secret: str | None = None
    claude_cli_path: str = "claude"
    claude_provider_mode: Literal[
        "auto",
        "anthropic",
        "bedrock",
        "mantle",
        "vertex",
        "foundry",
    ] = "auto"
    claude_model: str | None = None
    claude_default_sonnet_model: str | None = None
    claude_default_opus_model: str | None = None
    claude_default_haiku_model: str | None = None
    claude_base_url: str | None = None
    runtime_permission_mode: Literal[
        "default",
        "acceptEdits",
        "plan",
        "bypassPermissions",
        "dontAsk",
        "auto",
    ] = "acceptEdits"
    enable_direct_file_tools: bool = True
    scrub_provider_credentials_in_subprocesses: bool = False

    aws_region: str | None = None
    bedrock_base_url: str | None = None
    bedrock_bearer_token: str | None = None
    use_bedrock_mantle: bool = False
    enable_bedrock_invoke_api: bool = False
    bedrock_mantle_base_url: str | None = None

    vertex_project_id: str | None = None
    vertex_base_url: str | None = None
    cloud_ml_region: str | None = None

    foundry_resource: str | None = None
    foundry_base_url: str | None = None
    foundry_api_key: str | None = None

    local_insights_mcp_enabled: bool = True
    github_mcp_enabled: bool = False
    github_token: str | None = None
    github_mcp_command: str = "npx"
    github_mcp_args: str = "-y @modelcontextprotocol/server-github"
    remote_mcp_enabled: bool = False
    remote_mcp_name: str = "external-delivery-api"
    remote_mcp_type: Literal["http", "sse"] = "http"
    remote_mcp_url: str | None = None
    remote_mcp_auth_header: str = "Authorization"
    remote_mcp_bearer_token: str | None = None
    ui_show_developer_panel: bool = False
    ui_show_mode_picker: bool = False
    ui_show_subagents: bool = False
    ui_show_document_panel: bool = True
    ui_show_suggested_prompts: bool = True
    ui_exposed_modes: str = "agent"
    ui_exposed_subagents: str = ""

    project_root: Path = Path(__file__).resolve().parents[2]

    @property
    def resolved_backend_url(self) -> str:
        return self.backend_url or f"http://{self.api_host}:{self.api_port}"

    @property
    def resolved_auth_secret(self) -> str:
        if self.auth_secret and self.auth_secret.strip():
            return self.auth_secret.strip()
        seed = f"{self.project_root.resolve()}::{self.auth_username}::{self.auth_password}::data-transform-agent"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    @property
    def resolved_claude_cli_path(self) -> str | None:
        cli_path = Path(self.claude_cli_path)
        if cli_path.is_absolute():
            return str(cli_path) if cli_path.exists() else None
        return shutil.which(self.claude_cli_path)

    @property
    def anthropic_api_key_configured(self) -> bool:
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            return False
        return not key.startswith("your-")

    @property
    def provider_env_detected(self) -> dict[str, bool]:
        return {
            "bedrock": bool(self.aws_region or os.environ.get("CLAUDE_CODE_USE_BEDROCK")),
            "mantle": bool(self.use_bedrock_mantle or os.environ.get("CLAUDE_CODE_USE_MANTLE")),
            "vertex": bool(self.vertex_project_id or os.environ.get("CLAUDE_CODE_USE_VERTEX")),
            "foundry": bool(
                self.foundry_resource
                or self.foundry_base_url
                or os.environ.get("CLAUDE_CODE_USE_FOUNDRY")
            ),
        }

    @property
    def storage_root(self) -> Path:
        return self.project_root / "storage"

    @property
    def sessions_root(self) -> Path:
        return self.storage_root / "sessions"

    @property
    def templates_root(self) -> Path:
        return self.project_root / "templates"

    @property
    def plugin_root(self) -> Path:
        return self.project_root / "claude-plugins"

    @property
    def local_insights_server_path(self) -> Path:
        return self.project_root / "scripts" / "mcp" / "project_insights_server.py"

    @property
    def github_mcp_args_list(self) -> list[str]:
        return shlex.split(self.github_mcp_args)

    @property
    def hook_audit_path(self) -> Path:
        return self.storage_root / ".hook-audit.jsonl"

    @property
    def ui_exposed_modes_list(self) -> list[str]:
        return [item.strip() for item in self.ui_exposed_modes.split(",") if item.strip()]

    @property
    def ui_exposed_subagents_list(self) -> list[str]:
        return [item.strip() for item in self.ui_exposed_subagents.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
