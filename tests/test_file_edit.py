"""Tests for FileEditTool."""

import pytest

from src.tools.builtin.file_edit import FileEditTool


class TestFileEditTool:
    def test_replace_unique_match(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def hello():\n    print('hi')\n", encoding="utf-8")

        tool = FileEditTool()
        result = tool.execute(
            path=str(f),
            old_string="print('hi')",
            new_string="print('hello')",
        )
        assert "已替换" in result
        assert f.read_text(encoding="utf-8") == "def hello():\n    print('hello')\n"

    def test_replace_multiline_block(self, tmp_path):
        f = tmp_path / "code.py"
        original = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        f.write_text(original, encoding="utf-8")

        tool = FileEditTool()
        tool.execute(
            path=str(f),
            old_string="def foo():\n    pass\n",
            new_string="def foo():\n    return 42\n",
        )
        assert f.read_text(encoding="utf-8") == "def foo():\n    return 42\n\ndef bar():\n    pass\n"

    def test_old_string_not_found(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("hello world\n", encoding="utf-8")

        tool = FileEditTool()
        with pytest.raises(ValueError, match="未找到"):
            tool.execute(
                path=str(f),
                old_string="nonexistent text",
                new_string="replacement",
            )

    def test_multiple_matches_raises(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("x = 1\nx = 1\n", encoding="utf-8")

        tool = FileEditTool()
        with pytest.raises(ValueError, match="2 次"):
            tool.execute(
                path=str(f),
                old_string="x = 1",
                new_string="x = 2",
            )

    def test_file_not_found(self):
        tool = FileEditTool()
        with pytest.raises(FileNotFoundError, match="文件不存在"):
            tool.execute(
                path="/nonexistent/file.txt",
                old_string="a",
                new_string="b",
            )

    def test_directory_raises(self, tmp_path):
        tool = FileEditTool()
        with pytest.raises(IsADirectoryError):
            tool.execute(
                path=str(tmp_path),
                old_string="a",
                new_string="b",
            )

    def test_replace_with_empty_string(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("keep this\nremove this\nkeep this\n", encoding="utf-8")

        tool = FileEditTool()
        tool.execute(
            path=str(f),
            old_string="remove this\n",
            new_string="",
        )
        assert f.read_text(encoding="utf-8") == "keep this\nkeep this\n"

    def test_replace_creates_new_content(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("placeholder\n", encoding="utf-8")

        tool = FileEditTool()
        tool.execute(
            path=str(f),
            old_string="placeholder",
            new_string="line1\nline2\nline3",
        )
        assert f.read_text(encoding="utf-8") == "line1\nline2\nline3\n"


class TestFileEditSandbox:
    def test_edit_outside_work_dir_rejected(self, tmp_path):
        work_dir = tmp_path / "project"
        work_dir.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("hello\n", encoding="utf-8")

        tool = FileEditTool()
        tool.work_dir = work_dir
        with pytest.raises(PermissionError, match="超出工作目录"):
            tool.execute(
                path=str(outside), old_string="hello", new_string="bye"
            )
        assert outside.read_text(encoding="utf-8") == "hello\n"
