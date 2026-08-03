"""Tests for GlobTool."""

import pytest

from src.tools.builtin.glob import GlobTool


class TestGlobTool:
    def test_find_python_files(self, tmp_path):
        (tmp_path / "a.py").write_text("# a")
        (tmp_path / "b.py").write_text("# b")
        (tmp_path / "c.txt").write_text("c")

        tool = GlobTool()
        result = tool.execute(pattern="*.py", path=str(tmp_path))
        assert "a.py" in result
        assert "b.py" in result
        assert "c.txt" not in result

    def test_recursive_glob(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("# deep")
        (tmp_path / "top.py").write_text("# top")

        tool = GlobTool()
        result = tool.execute(pattern="**/*.py", path=str(tmp_path))
        assert "deep.py" in result
        assert "top.py" in result

    def test_no_matches(self, tmp_path):
        tool = GlobTool()
        result = tool.execute(pattern="*.nonexistent", path=str(tmp_path))
        assert "未找到" in result

    def test_nonexistent_path(self):
        tool = GlobTool()
        with pytest.raises(FileNotFoundError):
            tool.execute(pattern="*", path="/nonexistent/path/xyz")

    def test_results_capped(self, tmp_path):
        for i in range(150):
            (tmp_path / f"file_{i}.txt").write_text("x")

        tool = GlobTool()
        result = tool.execute(pattern="*.txt", path=str(tmp_path))
        # Should have a truncation notice since 150 > 100.
        assert "仅显示前 100" in result
