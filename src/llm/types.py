"""Core data types for LLM communication.

These types provide a provider-agnostic representation of messages,
tool calls, and tool results. Each LLM provider (Claude, OpenAI) is
responsible for converting between these unified types and its own
API-specific format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """The result of executing a tool call."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class Usage:
    """Token usage reported by the provider for a single LLM call."""

    input_tokens: int
    output_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Usage:
        return cls(
            input_tokens=d["input_tokens"],
            output_tokens=d["output_tokens"],
        )


@dataclass
class Message:
    """A unified message in the conversation.

    - role "user": content is the user's text input.
    - role "assistant": content is the LLM's text response (may be empty
      if the response consists solely of tool calls). tool_calls holds
      any tool invocations the LLM requested. usage holds the token usage
      reported for that assistant response (for cost tracking).
    - role "tool": content is the tool execution result. tool_call_id
      links it back to the originating ToolCall.
    """

    role: str  # "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # only for role="tool"
    usage: Usage | None = None  # only for role="assistant"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (for persistence/debugging)."""
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.usage is not None:
            d["usage"] = self.usage.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Message:
        """Deserialize from a plain dict (inverse of to_dict)."""
        tool_calls = [
            ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
            for tc in d.get("tool_calls", [])
        ]
        usage = Usage.from_dict(d["usage"]) if d.get("usage") else None
        return cls(
            role=d["role"],
            content=d.get("content", ""),
            tool_calls=tool_calls,
            tool_call_id=d.get("tool_call_id"),
            usage=usage,
        )

    @classmethod
    def user(cls, content: str) -> Message:
        return cls(role="user", content=content)

    @classmethod
    def assistant(
        cls,
        content: str = "",
        tool_calls: list[ToolCall] | None = None,
        usage: Usage | None = None,
    ) -> Message:
        return cls(
            role="assistant",
            content=content,
            tool_calls=tool_calls or [],
            usage=usage,
        )

    @classmethod
    def tool(cls, tool_call_id: str, content: str, is_error: bool = False) -> Message:
        # Encode error status as a prefix so providers that don't have a
        # native error field can still convey it in the content.
        prefix = "[ERROR] " if is_error else ""
        return cls(
            role="tool",
            content=f"{prefix}{content}",
            tool_call_id=tool_call_id,
        )


@dataclass
class ToolSpec:
    """A tool specification sent to the LLM so it knows what tools are available."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
