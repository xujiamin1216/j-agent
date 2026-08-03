"""Abstract LLM provider interface.

Each provider (Claude, OpenAI) implements this interface, converting between
the unified Message/ToolSpec types and its own API format. The agent loop
interacts only with LLMProvider, so switching models requires no changes
to the agent code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.llm.types import Message, ToolSpec


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
    ) -> Message:
        """Send a chat request and return the assistant's response.

        Args:
            messages: The conversation history (excluding system prompt).
            tools: Available tools the LLM may call, or None for no tools.
            system: Optional system prompt to set the agent's behavior.

        Returns:
            An assistant Message containing text content and/or tool_calls.
        """
        ...
