"""FileWriteTool -- write or append content to a file.

Creates the file (and parent directories) if they don't exist. By
default, overwrites the file; set ``append=True`` to append instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.permission.risk import RiskLevel
from src.tools.base import Tool


class FileWriteTool(Tool):
    name = "file_write"
    risk_level = RiskLevel.CONFIRM
    description = (
        "Write content to a file. Creates parent directories if needed. "
        "Set 'append' to true to append instead of overwrite."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file.",
            },
            "content": {
                "type": "string",
                "description": "The text content to write.",
            },
            "append": {
                "type": "boolean",
                "description": "If true, append to the file instead of overwriting. Default: false.",
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def execute(
        self,
        *,
        path: str,
        content: str,
        append: bool = False,
        **kwargs: Any,
    ) -> str:
        p = self._resolve_path(path)

        # Create parent directories if they don't exist.
        p.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)

        byte_count = len(content.encode("utf-8"))
        action = "追加" if append else "写入"
        return f"已{action} {byte_count} 字节到 {path}"
