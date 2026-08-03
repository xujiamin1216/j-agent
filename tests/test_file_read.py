"""Tests for FileReadTool."""

import pytest

from src.tools.builtin.file_read import FileReadTool


class TestFileReadTool:
    def test_read_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line one\nline two\nline three\n", encoding="utf-8")

        tool = FileReadTool()
        result = tool.execute(path=str(f))
        assert "line one" in result
        assert "line two" in result
        assert "line three" in result
        # Line numbers should be present.
        assert "1" in result and "2" in result and "3" in result

    def test_file_not_found(self):
        tool = FileReadTool()
        with pytest.raises(FileNotFoundError, match="文件不存在"):
            tool.execute(path="/nonexistent/path/file.txt")

    def test_read_directory_raises(self, tmp_path):
        tool = FileReadTool()
        with pytest.raises(IsADirectoryError):
            tool.execute(path=str(tmp_path))

    def test_offset(self, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("L1\nL2\nL3\nL4\nL5\n", encoding="utf-8")

        tool = FileReadTool()
        result = tool.execute(path=str(f), offset=3)
        assert "L3" in result
        assert "L4" in result
        assert "L5" in result
        assert "L1" not in result
        assert "L2" not in result

    def test_limit_truncation(self, tmp_path):
        content = "\n".join(f"line {i}" for i in range(1, 101))
        f = tmp_path / "big.txt"
        f.write_text(content + "\n", encoding="utf-8")

        tool = FileReadTool()
        result = tool.execute(path=str(f), limit=10)
        assert "line 1" in result
        assert "line 10" in result
        assert "line 11" not in result
        assert "未显示" in result

    def test_offset_beyond_end(self, tmp_path):
        f = tmp_path / "small.txt"
        f.write_text("only line\n", encoding="utf-8")

        tool = FileReadTool()
        result = tool.execute(path=str(f), offset=999)
        assert "超出范围" in result
