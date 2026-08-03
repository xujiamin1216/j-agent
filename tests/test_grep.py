"""Tests for GrepTool."""

import pytest

from src.tools.builtin.grep import GrepTool


class TestGrepTool:
    def test_find_pattern(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("import os\nimport sys\nprint('hello')\n", encoding="utf-8")

        tool = GrepTool()
        result = tool.execute(pattern="import", path=str(tmp_path))
        assert "import os" in result
        assert "import sys" in result
        assert f.name in result

    def test_regex_pattern(self, tmp_path):
        f = tmp_path / "nums.txt"
        f.write_text("abc 123\ndef 456\nghi 789\n", encoding="utf-8")

        tool = GrepTool()
        result = tool.execute(pattern=r"\d{3}", path=str(tmp_path))
        assert "123" in result
        assert "456" in result
        assert "789" in result

    def test_no_matches(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("nothing here\n", encoding="utf-8")

        tool = GrepTool()
        result = tool.execute(pattern="nonexistent_pattern", path=str(tmp_path))
        assert "未找到" in result

    def test_include_filter(self, tmp_path):
        (tmp_path / "match.py").write_text("target_line\n", encoding="utf-8")
        (tmp_path / "skip.txt").write_text("target_line\n", encoding="utf-8")

        tool = GrepTool()
        result = tool.execute(
            pattern="target", path=str(tmp_path), include="*.py"
        )
        assert "match.py" in result
        assert "skip.txt" not in result

    def test_single_file_search(self, tmp_path):
        f = tmp_path / "single.py"
        f.write_text("line1\nFOUND\nline3\n", encoding="utf-8")

        tool = GrepTool()
        result = tool.execute(pattern="FOUND", path=str(f))
        assert "FOUND" in result
        assert "single.py" in result

    def test_line_numbers_in_output(self, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("first\nsecond\nthird\n", encoding="utf-8")

        tool = GrepTool()
        result = tool.execute(pattern="third", path=str(f))
        assert ":3:" in result

    def test_skips_unwanted_dirs(self, tmp_path):
        # Create a __pycache__ dir with a matching file -- should be skipped.
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "cached.py").write_text("should_not_appear\n", encoding="utf-8")
        (tmp_path / "main.py").write_text("should_appear\n", encoding="utf-8")

        tool = GrepTool()
        result = tool.execute(pattern="should", path=str(tmp_path))
        assert "main.py" in result
        assert "cached.py" not in result
