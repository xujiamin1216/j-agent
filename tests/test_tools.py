"""Tests for the tool framework."""

import pytest

from src.tools.base import Tool, ToolRegistry
from src.llm.types import ToolResult


class _DummyTool(Tool):
    name = "dummy"
    description = "A dummy tool for testing."
    parameters = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }

    def execute(self, *, value: str, **kwargs) -> str:
        if value == "error":
            raise ValueError("intentional error")
        return f"echo: {value}"


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = _DummyTool()
        reg.register(tool)
        assert reg.get("dummy") is tool

    def test_register_duplicate_raises(self):
        reg = ToolRegistry()
        reg.register(_DummyTool())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_DummyTool())

    def test_execute_success(self):
        reg = ToolRegistry()
        reg.register(_DummyTool())
        result = reg.execute("dummy", {"value": "hello"})
        assert result.content == "echo: hello"
        assert result.is_error is False

    def test_execute_error_caught(self):
        reg = ToolRegistry()
        reg.register(_DummyTool())
        result = reg.execute("dummy", {"value": "error"})
        assert result.is_error is True
        assert "ValueError" in result.content

    def test_execute_unknown_tool(self):
        reg = ToolRegistry()
        result = reg.execute("nonexistent", {})
        assert result.is_error is True
        assert "Unknown tool" in result.content

    def test_to_specs(self):
        reg = ToolRegistry()
        reg.register(_DummyTool())
        specs = reg.to_specs()
        assert len(specs) == 1
        assert specs[0].name == "dummy"
        assert specs[0].description == "A dummy tool for testing."

    def test_names(self):
        reg = ToolRegistry()
        reg.register(_DummyTool())
        assert reg.names() == ["dummy"]


class TestToolRegistryValidation:
    """Tests for parameter validation in ToolRegistry.execute()."""

    def test_validation_error_returns_is_error(self):
        reg = ToolRegistry()
        reg.register(_DummyTool())
        # Missing required "value" field.
        result = reg.execute("dummy", {})
        assert result.is_error is True
        assert "参数校验失败" in result.content
        assert "value" in result.content

    def test_wrong_type_returns_is_error(self):
        reg = ToolRegistry()
        reg.register(_DummyTool())
        # "value" should be string, not int.
        result = reg.execute("dummy", {"value": 123})
        assert result.is_error is True
        assert "参数校验失败" in result.content

    def test_valid_arguments_execute_normally(self):
        reg = ToolRegistry()
        reg.register(_DummyTool())
        result = reg.execute("dummy", {"value": "hello"})
        assert result.is_error is False
        assert result.content == "echo: hello"


class TestToolRegistryTruncation:
    """Tests for output truncation in ToolRegistry.execute()."""

    def test_long_output_truncated(self):
        from src.tools.base import MAX_OUTPUT_CHARS

        class _LongTool(Tool):
            name = "long"
            description = "Returns a very long string."
            parameters = {
                "type": "object",
                "properties": {},
            }

            def execute(self, **kwargs) -> str:
                return "x" * (MAX_OUTPUT_CHARS + 1000)

        reg = ToolRegistry()
        reg.register(_LongTool())
        result = reg.execute("long", {})
        assert result.is_error is False
        assert "截断" in result.content
        assert len(result.content) < MAX_OUTPUT_CHARS + 1000

    def test_short_output_not_truncated(self):
        reg = ToolRegistry()
        reg.register(_DummyTool())
        result = reg.execute("dummy", {"value": "hello"})
        assert "截断" not in result.content
