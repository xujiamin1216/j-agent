"""Claude (Anthropic) LLM provider implementation.

Converts unified Message/ToolSpec types to the Anthropic API format and
parses the response back into a unified Message.
"""

from __future__ import annotations

import anthropic

from src.llm.base import LLMProvider
from src.llm.types import Message, ToolCall, ToolSpec, Usage


class ClaudeProvider(LLMProvider):
    """LLM provider backed by the Anthropic Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        base_url: str | None = None,
    ) -> None:
        client_kwargs: dict = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = anthropic.Anthropic(**client_kwargs)
        self._model = model
        self._max_tokens = max_tokens

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
    ) -> Message:
        # Convert unified messages to Anthropic format.
        anthropic_messages = [self._to_anthropic_msg(m) for m in messages]

        kwargs: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": anthropic_messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [self._to_anthropic_tool(t) for t in tools]

        response = self._client.messages.create(**kwargs)

        # Extract text content and tool calls from the response.
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        usage = None
        if getattr(response, "usage", None) is not None:
            usage = Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        return Message.assistant(
            content="\n".join(text_parts),
            tool_calls=tool_calls,
            usage=usage,
        )

    def _to_anthropic_msg(self, msg: Message) -> dict:
        """Convert a unified Message to Anthropic API format."""
        if msg.role == "user":
            return {"role": "user", "content": msg.content}

        if msg.role == "assistant":
            if msg.tool_calls:
                # Assistant message with tool calls: build content blocks.
                content: list[dict] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                return {"role": "assistant", "content": content}
            return {"role": "assistant", "content": msg.content}

        if msg.role == "tool":
            # Tool result messages use role "user" with tool_result content.
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                ],
            }

        raise ValueError(f"Unknown message role: {msg.role}")

    def _to_anthropic_tool(self, spec: ToolSpec) -> dict:
        """Convert a ToolSpec to Anthropic's tool definition format."""
        return {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.parameters,
        }
