"""Tests for MemoryTool."""

from pathlib import Path

import pytest

from src.tools.base import Tool, ToolRegistry
from src.tools.builtin.memory import MemoryTool
from src.tools.discovery import discover_builtin_tools


@pytest.fixture
def memory_tool(tmp_path, monkeypatch):
    """Create a MemoryTool with isolated storage."""
    memory_file = tmp_path / "memory.json"

    def _mock_init(self, memory_file_arg=None):
        from src.memory.memory_store import MemoryStore
        self._path = memory_file
        self._data = MemoryStore._load(self)

    monkeypatch.setattr("src.tools.builtin.memory.MemoryStore.__init__", _mock_init)
    return MemoryTool()


class TestMemoryToolActions:
    def test_save_action(self, memory_tool):
        result = memory_tool.execute(action="save", key="name", value="j-agent")
        assert "已保存" in result
        assert "name" in result

    def test_read_action(self, memory_tool):
        memory_tool.execute(action="save", key="name", value="j-agent")
        result = memory_tool.execute(action="read", key="name")
        assert result == "j-agent"

    def test_read_nonexistent_raises(self, memory_tool):
        with pytest.raises(KeyError, match="未找到记忆"):
            memory_tool.execute(action="read", key="nonexistent")

    def test_list_action_empty(self, memory_tool):
        result = memory_tool.execute(action="list")
        assert "暂无" in result

    def test_list_action_with_data(self, memory_tool):
        memory_tool.execute(action="save", key="a", value="1")
        memory_tool.execute(action="save", key="b", value="2")
        result = memory_tool.execute(action="list")
        assert "a" in result
        assert "b" in result

    def test_delete_action(self, memory_tool):
        memory_tool.execute(action="save", key="key", value="value")
        result = memory_tool.execute(action="delete", key="key")
        assert "已删除" in result
        with pytest.raises(KeyError):
            memory_tool.execute(action="read", key="key")


class TestMemoryToolValidation:
    def test_save_missing_key_raises(self, memory_tool):
        with pytest.raises(ValueError, match="key"):
            memory_tool.execute(action="save", value="v")

    def test_save_missing_value_raises(self, memory_tool):
        with pytest.raises(ValueError, match="value"):
            memory_tool.execute(action="save", key="k")

    def test_unknown_action_raises(self, memory_tool):
        with pytest.raises(ValueError, match="未知操作"):
            memory_tool.execute(action="foo")


class TestMemoryToolDiscovery:
    def test_auto_discovery_includes_memory(self):
        tools = discover_builtin_tools()
        names = {t.name for t in tools}
        assert "memory" in names

    def test_is_tool_instance(self):
        tools = discover_builtin_tools()
        memory_tool = next(t for t in tools if t.name == "memory")
        assert isinstance(memory_tool, Tool)

    def test_tool_spec_valid(self):
        tool = MemoryTool()
        spec = tool.to_spec()
        assert spec.name == "memory"
        assert spec.description
        assert "action" in spec.parameters["properties"]
        assert "key" in spec.parameters["properties"]
        assert "value" in spec.parameters["properties"]
        assert spec.parameters["required"] == ["action"]


class TestMemoryToolWorkDir:
    def test_work_dir_isolates_memory(self, tmp_path: Path):
        """MemoryTool with work_dir stores data in <work_dir>/.j-agent/memory.json."""
        work_dir = tmp_path / "project"
        work_dir.mkdir()

        tool = MemoryTool()
        tool.work_dir = work_dir

        tool.execute(action="save", key="key1", value="value1")

        memory_file = work_dir / ".j-agent" / "memory.json"
        assert memory_file.exists()
        assert "key1" in memory_file.read_text(encoding="utf-8")

    def test_different_work_dirs_isolated(self, tmp_path: Path):
        """Two MemoryTools with different work_dirs have separate storage."""
        dir_a = tmp_path / "project-a"
        dir_b = tmp_path / "project-b"
        dir_a.mkdir()
        dir_b.mkdir()

        tool_a = MemoryTool()
        tool_a.work_dir = dir_a
        tool_b = MemoryTool()
        tool_b.work_dir = dir_b

        tool_a.execute(action="save", key="key", value="from-a")
        tool_b.execute(action="save", key="key", value="from-b")

        assert tool_a.execute(action="read", key="key") == "from-a"
        assert tool_b.execute(action="read", key="key") == "from-b"

    def test_registry_sets_work_dir(self, tmp_path: Path):
        """ToolRegistry sets work_dir on registered tools."""
        work_dir = tmp_path / "project"
        work_dir.mkdir()

        registry = ToolRegistry(work_dir=work_dir)
        tool = MemoryTool()
        registry.register(tool)

        assert tool.work_dir == work_dir
