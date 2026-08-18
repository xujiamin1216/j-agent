"""OpenAI LLM provider implementation.

Converts unified Message/ToolSpec types to the OpenAI API format and
parses the response back into a unified Message.
"""

from __future__ import annotations

import json

from openai import OpenAI

from src.llm.base import LLMProvider
from src.llm.types import Message, ToolCall, ToolSpec, Usage


class OpenAIProvider(LLMProvider):
    """LLM provider backed by the OpenAI API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        max_tokens: int = 4096,
        base_url: str | None = None,
    ) -> None:
        client_kwargs: dict = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = OpenAI(**client_kwargs)
        self._model = model
        self._max_tokens = max_tokens

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
    ) -> Message:
        # Build the OpenAI messages list, prepending system prompt if present.
        oai_messages: list[dict] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        oai_messages.extend(self._to_openai_msg(m) for m in messages)

        kwargs: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": oai_messages,
        }
        if tools:
            kwargs["tools"] = [self._to_openai_tool(t) for t in tools]

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        # Parse tool calls if present.
        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        usage = None
        if getattr(response, "usage", None) is not None:
            usage = Usage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )

        return Message.assistant(
            content=msg.content or "",
            tool_calls=tool_calls,
            usage=usage,
        )

    def _to_openai_msg(self, msg: Message) -> dict:
        """Convert a unified Message to OpenAI API format."""
        if msg.role == "user":
            return {"role": "user", "content": msg.content}

        if msg.role == "assistant":
            result: dict = {"role": "assistant", "content": msg.content or None}
            if msg.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            return result

        if msg.role == "tool":
            return {
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content,
            }

        raise ValueError(f"Unknown message role: {msg.role}")

    def _to_openai_tool(self, spec: ToolSpec) -> dict:
        """Convert a ToolSpec to OpenAI's function tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }
