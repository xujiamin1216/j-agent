"""Tests for tool auto-discovery."""

from src.tools.base import Tool
from src.tools.discovery import discover_builtin_tools


class TestDiscovery:
    def test_discovers_all_builtin_tools(self):
        tools = discover_builtin_tools()
        names = {t.name for t in tools}
        # All seven built-in tools should be discovered.
        assert names == {"file_read", "file_write", "file_edit", "bash", "glob", "grep", "memory"}

    def test_all_discovered_are_tool_instances(self):
        tools = discover_builtin_tools()
        for tool in tools:
            assert isinstance(tool, Tool)

    def test_no_duplicate_tools(self):
        tools = discover_builtin_tools()
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), "Duplicate tool names discovered"

    def test_each_tool_has_valid_spec(self):
        tools = discover_builtin_tools()
        for tool in tools:
            spec = tool.to_spec()
            assert spec.name == tool.name
            assert spec.description
            assert "type" in spec.parameters
