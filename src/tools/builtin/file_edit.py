"""FileEditTool -- targeted string replacement in files.

Replaces a unique occurrence of *old_string* with *new_string* in a file.
If *old_string* appears multiple times (or not at all), the tool returns
an error -- the caller must provide enough surrounding context to make
the match unambiguous.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.permission.risk import RiskLevel
from src.tools.base import Tool


class FileEditTool(Tool):
    name = "file_edit"
    risk_level = RiskLevel.CONFIRM
    description = (
        "Replace a unique string in a file. The 'old_string' must appear "
        "exactly once in the file; if it appears multiple times, provide "
        "more context to make it unique. Use this for targeted edits "
        "instead of rewriting the entire file. Access is restricted to files "
        "within the working directory."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file, relative to the working directory (or absolute within it).",
            },
            "old_string": {
                "type": "string",
                "description": "The exact text to find and replace. Must be unique in the file.",
            },
            "new_string": {
                "type": "string",
                "description": "The replacement text.",
            },
        },
        "required": ["path", "old_string", "new_string"],
        "additionalProperties": False,
    }

    def execute(
        self,
        *,
        path: str,
        old_string: str,
        new_string: str,
        **kwargs: Any,
    ) -> str:
        p = self._resolve_work_path(path)

        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        if p.is_dir():
            raise IsADirectoryError(f"路径是目录而非文件: {path}")

        content = p.read_text(encoding="utf-8")

        count = content.count(old_string)
        if count == 0:
            raise ValueError(
                f"未找到要替换的文本。请确认 old_string 是否与文件内容完全一致。"
            )
        if count > 1:
            raise ValueError(
                f"old_string 在文件中出现 {count} 次，无法唯一定位。"
                f"请提供更多上下文使其唯一。"
            )

        new_content = content.replace(old_string, new_string)
        p.write_text(new_content, encoding="utf-8")

        return f"已替换 {path} 中的 1 处文本"