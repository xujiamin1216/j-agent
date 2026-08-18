"""Tests for LLM type definitions."""

from src.llm.types import Message, ToolCall, ToolResult, ToolSpec, Usage


class TestMessage:
    def test_user_message(self):
        msg = Message.user("hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.tool_calls == []

    def test_assistant_message_with_tool_calls(self):
        tc = ToolCall(id="tc1", name="echo", arguments={"text": "hi"})
        msg = Message.assistant(content="thinking...", tool_calls=[tc])
        assert msg.role == "assistant"
        assert msg.content == "thinking..."
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "echo"

    def test_assistant_message_empty(self):
        msg = Message.assistant()
        assert msg.role == "assistant"
        assert msg.content == ""
        assert msg.tool_calls == []

    def test_tool_message(self):
        msg = Message.tool("tc1", "result text")
        assert msg.role == "tool"
        assert msg.content == "result text"
        assert msg.tool_call_id == "tc1"

    def test_tool_message_error(self):
        msg = Message.tool("tc1", "something failed", is_error=True)
        assert msg.content.startswith("[ERROR]")

    def test_to_dict_user(self):
        msg = Message.user("hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "hello"}

    def test_to_dict_with_tool_calls(self):
        tc = ToolCall(id="tc1", name="echo", arguments={"text": "hi"})
        msg = Message.assistant(tool_calls=[tc])
        d = msg.to_dict()
        assert "tool_calls" in d
        assert d["tool_calls"][0]["name"] == "echo"


class TestMessageFromDict:
    def test_from_dict_user(self):
        original = Message.user("hello")
        restored = Message.from_dict(original.to_dict())
        assert restored.role == "user"
        assert restored.content == "hello"
        assert restored.tool_calls == []
        assert restored.tool_call_id is None

    def test_from_dict_assistant_with_tool_calls(self):
        tc = ToolCall(id="tc1", name="echo", arguments={"text": "hi"})
        original = Message.assistant(content="thinking...", tool_calls=[tc])
        restored = Message.from_dict(original.to_dict())
        assert restored.role == "assistant"
        assert restored.content == "thinking..."
        assert len(restored.tool_calls) == 1
        assert restored.tool_calls[0].id == "tc1"
        assert restored.tool_calls[0].name == "echo"
        assert restored.tool_calls[0].arguments == {"text": "hi"}

    def test_from_dict_assistant_empty(self):
        original = Message.assistant()
        restored = Message.from_dict(original.to_dict())
        assert restored.role == "assistant"
        assert restored.content == ""
        assert restored.tool_calls == []

    def test_from_dict_tool(self):
        original = Message.tool("tc1", "result text")
        restored = Message.from_dict(original.to_dict())
        assert restored.role == "tool"
        assert restored.content == "result text"
        assert restored.tool_call_id == "tc1"

    def test_from_dict_tool_error_preserved(self):
        original = Message.tool("tc1", "something failed", is_error=True)
        restored = Message.from_dict(original.to_dict())
        assert restored.content.startswith("[ERROR]")

    def test_from_dict_missing_optional_fields(self):
        d = {"role": "user", "content": "hi"}
        restored = Message.from_dict(d)
        assert restored.role == "user"
        assert restored.content == "hi"
        assert restored.tool_calls == []
        assert restored.tool_call_id is None

    def test_round_trip_all_types(self):
        messages = [
            Message.user("hello"),
            Message.assistant("hi", [ToolCall(id="tc1", name="echo", arguments={"x": 1})]),
            Message.tool("tc1", "result"),
            Message.assistant("done"),
        ]
        for msg in messages:
            restored = Message.from_dict(msg.to_dict())
            assert restored.role == msg.role
            assert restored.content == msg.content
            assert len(restored.tool_calls) == len(msg.tool_calls)
            assert restored.tool_call_id == msg.tool_call_id


class TestToolSpec:
    def test_to_dict(self):
        spec = ToolSpec(
            name="echo",
            description="Echo tool",
            parameters={"type": "object", "properties": {}},
        )
        d = spec.to_dict()
        assert d["name"] == "echo"
        assert d["description"] == "Echo tool"
        assert d["parameters"]["type"] == "object"


class TestUsage:
    def test_to_dict(self):
        usage = Usage(input_tokens=10, output_tokens=20)
        assert usage.to_dict() == {"input_tokens": 10, "output_tokens": 20}

    def test_from_dict(self):
        usage = Usage.from_dict({"input_tokens": 10, "output_tokens": 20})
        assert usage.input_tokens == 10
        assert usage.output_tokens == 20

    def test_message_usage_round_trip(self):
        original = Message.assistant("hi", usage=Usage(10, 20))
        restored = Message.from_dict(original.to_dict())
        assert restored.usage is not None
        assert restored.usage.input_tokens == 10
        assert restored.usage.output_tokens == 20

    def test_message_without_usage(self):
        msg = Message.assistant("hi")
        assert msg.usage is None
        assert "usage" not in msg.to_dict()
