"""Shared runtime configuration helpers."""

from __future__ import annotations

import os

DEFAULT_AGENT_NAME = "hmrc-data-transformation-agent"
FALLBACK_AGENT_NAME = "agentcore_agent"


def normalize_agent_name(raw_name: str) -> str:
    """Normalize an agent name to the shared runtime-safe format."""
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw_name.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    cleaned = cleaned.strip("_").lower()
    return cleaned[:47] or FALLBACK_AGENT_NAME


def resolve_agent_name(default_name: str = DEFAULT_AGENT_NAME) -> str:
    """Resolve the shared agent name from env or project default."""
    return normalize_agent_name(os.getenv("AGENTCORE_AGENT_NAME", default_name))

