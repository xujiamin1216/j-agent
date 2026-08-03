"""Tests for LLM type definitions."""

from src.llm.types import Message, ToolCall, ToolSpec, ToolResult


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
