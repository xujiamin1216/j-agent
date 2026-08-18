"""Configuration management for j-agent.

Loads settings from environment variables and a .env file. The config
determines which LLM provider to use, which model to call, and where
to find API keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.permission.manager import PermissionMode

# File name for project-specific context loaded into the system prompt.
CONTEXT_FILE = "AGENT.md"

# File name for project-specific environment variable overrides.
CONFIG_FILE = ".j-agent.env"


def load_work_context() -> str:
    """Load work context from ``AGENT.md`` in the current working directory.

    Returns the file content as a string, or an empty string if the file
    does not exist or is empty.
    """
    path = Path.cwd() / CONTEXT_FILE
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    return text


@dataclass
class Config:
    """Runtime configuration for the agent."""

    provider: str  # "claude" | "openai"
    model: str
    api_key: str
    system_prompt: str
    max_tokens: int = 4096
    base_url: str | None = None  # None means use provider's default
    max_context_tokens: int = 100_000
    compress_ratio: float = 0.6
    summary_ratio: float = 0.1
    permission_mode: str = "auto"  # "auto" | "ask" | "yolo"

    @classmethod
    def from_env(cls) -> Config:
        """Build a Config from environment variables.

        Loads ``.env`` and ``.j-agent.env`` (with override) from the
        current working directory before reading environment variables.

        Required env vars:
            J_AGENT_PROVIDER: "claude" or "openai"
            J_AGENT_API_KEY: API key for the chosen provider
            J_AGENT_MODEL: model identifier (optional, defaults provided)

        For convenience, if J_AGENT_MODEL is not set, a sensible default
        for the chosen provider is used.
        """
        # Load .env from the current working directory if it exists.
        load_dotenv()
        # Load .j-agent.env, overriding .env values (project-specific precedence).
        load_dotenv(CONFIG_FILE, override=True)

        provider = os.getenv("J_AGENT_PROVIDER", "claude").lower()

        defaults = {
            "claude": "claude-sonnet-4-20250514",
            "openai": "gpt-4o",
        }

        model = os.getenv("J_AGENT_MODEL") or defaults.get(provider, "gpt-4o")

        api_key = os.getenv("J_AGENT_API_KEY")
        if not api_key:
            raise RuntimeError(
                "J_AGENT_API_KEY is not set. "
                "Please set it in your .env file or environment."
            )

        system_prompt = os.getenv(
            "J_AGENT_SYSTEM_PROMPT",
            "You are a helpful AI assistant. Use tools when appropriate to help the user.",
        )

        # Append work context from AGENT.md if available.
        work_context = load_work_context()
        if work_context:
            system_prompt = (
                f"{system_prompt}\n\n---\n\n"
                f"# 工作上下文 ({CONTEXT_FILE})\n\n{work_context}"
            )

        # Append skill descriptions for natural language triggering.
        from src.skills.discovery import build_skill_descriptions

        skill_descs = build_skill_descriptions(Path.cwd())
        if skill_descs:
            system_prompt = (
                f"{system_prompt}\n\n---\n\n"
                f"# Skills\n\n"
                f"You have access to the following skills. When a user's request "
                f"matches a skill's trigger conditions, invoke the `use_skill` tool "
                f"with the skill name BEFORE generating any other response about "
                f"the task.\n\n{skill_descs}"
            )

        max_tokens = int(os.getenv("J_AGENT_MAX_TOKENS", "4096"))

        base_url = os.getenv("J_AGENT_BASE_URL") or None

        max_context_tokens = int(os.getenv("J_AGENT_MAX_CONTEXT_TOKENS", "100000"))
        compress_ratio = float(os.getenv("J_AGENT_COMPRESS_RATIO", "0.6"))
        summary_ratio = float(os.getenv("J_AGENT_SUMMARY_RATIO", "0.1"))

        permission_mode = os.getenv("J_AGENT_PERMISSION_MODE", "auto").lower()
        if permission_mode not in PermissionMode.ALL:
            raise RuntimeError(
                f"J_AGENT_PERMISSION_MODE 无效: {permission_mode} "
                f"（可选: auto / ask / yolo）"
            )

        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            base_url=base_url,
            max_context_tokens=max_context_tokens,
            compress_ratio=compress_ratio,
            summary_ratio=summary_ratio,
            permission_mode=permission_mode,
        )


def create_data_dir() -> Path:
    """Ensure the j-agent data directory exists and return its path."""
    path = Path.home() / ".j-agent"
    path.mkdir(parents=True, exist_ok=True)
    return path
