"""LLM provider factory.

Creates the appropriate LLMProvider based on Config, keeping provider
instantiation logic out of the Agent class.
"""

from __future__ import annotations

from src.config import Config
from src.llm.base import LLMProvider
from src.llm.claude import ClaudeProvider
from src.llm.openai_provider import OpenAIProvider


def create_provider(config: Config) -> LLMProvider:
    """Instantiate the LLM provider based on config."""
    if config.provider == "claude":
        return ClaudeProvider(
            api_key=config.api_key,
            model=config.model,
            max_tokens=config.max_tokens,
            base_url=config.base_url,
        )
    elif config.provider == "openai":
        return OpenAIProvider(
            api_key=config.api_key,
            model=config.model,
            max_tokens=config.max_tokens,
            base_url=config.base_url,
        )
    else:
        raise ValueError(f"Unknown provider: {config.provider}")
