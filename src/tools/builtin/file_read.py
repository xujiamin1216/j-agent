"""FileReadTool -- read file contents with line numbers.

Reads a text file and returns its content with line-number prefixes
(``cat -n`` style). Supports reading a range of lines via *offset* and
*limit*, which is useful for large files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.tools.base import Tool


class FileReadTool(Tool):
    name = "file_read"
    description = (
        "Read the contents of a text file. Returns lines with line numbers. "
        "Use 'offset' to start from a specific line and 'limit' to cap the "
        "number of lines read (default 2000)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file.",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-based). Default: 1.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read. Default: 2000.",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def execute(
        self,
        *,
        path: str,
        offset: int | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> str:
        p = self._resolve_path(path)

        if not p.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        if p.is_dir():
            raise IsADirectoryError(f"路径是目录而非文件: {path}")

        start = max(offset or 1, 1)
        max_lines = limit or 2000

        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = p.read_text(encoding="utf-8", errors="replace")

        lines = text.splitlines()
        total = len(lines)

        start_idx = start - 1
        if start_idx >= total:
            return f"文件共 {total} 行, offset {start} 超出范围。"

        end_idx = min(start_idx + max_lines, total)
        selected = lines[start_idx:end_idx]

        numbered = [
            f"{start_idx + i + 1:>6}\t{line}" for i, line in enumerate(selected)
        ]

        result = "\n".join(numbered)

        if end_idx < total:
            result += f"\n\n... [仅显示 {start}-{end_idx} 行, 共 {total} 行, "
            result += f"还有 {total - end_idx} 行未显示]"

        return result
