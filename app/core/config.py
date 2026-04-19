import os
import shlex
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATA_TRANSFORM_AGENT_", extra="ignore")

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    ui_host: str = "127.0.0.1"
    ui_port: int = 5001
    backend_url: str | None = None
    claude_cli_path: str = "claude"

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

    project_root: Path = Path(__file__).resolve().parents[2]

    @property
    def resolved_backend_url(self) -> str:
        return self.backend_url or f"http://{self.api_host}:{self.api_port}"

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
