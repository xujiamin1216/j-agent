"""Tests for BashTool."""

import pytest

from src.tools.builtin.bash import BashTool


class TestBashTool:
    def test_simple_command(self):
        tool = BashTool()
        result = tool.execute(command="echo hello")
        assert "hello" in result
        assert "退出码: 0" in result

    def test_command_with_stderr(self):
        tool = BashTool()
        result = tool.execute(command="echo error_msg >&2")
        assert "error_msg" in result
        assert "stderr" in result

    def test_nonzero_exit_code(self):
        tool = BashTool()
        result = tool.execute(command="exit 1")
        assert "退出码: 1" in result

    def test_timeout(self):
        tool = BashTool()
        result = tool.execute(command="sleep 10", timeout=1)
        assert "超时" in result
        assert "1" in result

    def test_custom_cwd(self, tmp_path):
        tool = BashTool()
        result = tool.execute(command="pwd", cwd=str(tmp_path))
        assert str(tmp_path) in result

    def test_default_timeout_used(self):
        # Just verify it doesn't hang with default timeout on a quick command.
        tool = BashTool()
        result = tool.execute(command="echo fast")
        assert "fast" in result
