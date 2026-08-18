"""Tests for FileWriteTool."""

import pytest

from src.tools.builtin.file_write import FileWriteTool


class TestFileWriteTool:
    def test_write_new_file(self, tmp_path):
        f = tmp_path / "output.txt"
        tool = FileWriteTool()
        result = tool.execute(path=str(f), content="hello world")

        assert "写入" in result
        assert f.read_text(encoding="utf-8") == "hello world"

    def test_overwrite_existing_file(self, tmp_path):
        f = tmp_path / "existing.txt"
        f.write_text("old content", encoding="utf-8")

        tool = FileWriteTool()
        tool.execute(path=str(f), content="new content")
        assert f.read_text(encoding="utf-8") == "new content"

    def test_append_mode(self, tmp_path):
        f = tmp_path / "append.txt"
        f.write_text("first\n", encoding="utf-8")

        tool = FileWriteTool()
        tool.execute(path=str(f), content="second\n", append=True)
        assert f.read_text(encoding="utf-8") == "first\nsecond\n"

    def test_creates_parent_directories(self, tmp_path):
        f = tmp_path / "sub" / "dir" / "file.txt"
        tool = FileWriteTool()
        tool.execute(path=str(f), content="nested")
        assert f.read_text(encoding="utf-8") == "nested"

    def test_byte_count_in_result(self, tmp_path):
        f = tmp_path / "bytes.txt"
        tool = FileWriteTool()
        result = tool.execute(path=str(f), content="abc")
        # "abc" is 3 bytes.
        assert "3" in result

    def test_unicode_content(self, tmp_path):
        f = tmp_path / "unicode.txt"
        tool = FileWriteTool()
        tool.execute(path=str(f), content="你好世界")
        assert f.read_text(encoding="utf-8") == "你好世界"


class TestFileWriteSandbox:
    def test_write_outside_work_dir_rejected(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        outside = tmp_path / "outside.txt"

        tool = FileWriteTool()
        tool.work_dir = work_dir
        with pytest.raises(PermissionError, match="超出工作目录"):
            tool.execute(path=str(outside), content="nope")
        assert not outside.exists()

    def test_write_inside_work_dir_allowed(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()

        tool = FileWriteTool()
        tool.work_dir = work_dir
        tool.execute(path="out.txt", content="ok")
        assert (work_dir / "out.txt").read_text(encoding="utf-8") == "ok"
