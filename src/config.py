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

# Load .env from the current working directory if it exists.
load_dotenv()


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

    @classmethod
    def from_env(cls) -> Config:
        """Build a Config from environment variables.

        Required env vars:
            J_AGENT_PROVIDER: "claude" or "openai"
            J_AGENT_API_KEY: API key for the chosen provider
            J_AGENT_MODEL: model identifier (optional, defaults provided)

        For convenience, if J_AGENT_MODEL is not set, a sensible default
        for the chosen provider is used.
        """
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

        max_tokens = int(os.getenv("J_AGENT_MAX_TOKENS", "4096"))

        base_url = os.getenv("J_AGENT_BASE_URL") or None

        max_context_tokens = int(os.getenv("J_AGENT_MAX_CONTEXT_TOKENS", "100000"))
        compress_ratio = float(os.getenv("J_AGENT_COMPRESS_RATIO", "0.6"))
        summary_ratio = float(os.getenv("J_AGENT_SUMMARY_RATIO", "0.1"))

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
        )


def create_data_dir() -> Path:
    """Ensure the j-agent data directory exists and return its path."""
    path = Path.home() / ".j-agent"
    path.mkdir(parents=True, exist_ok=True)
    return path
