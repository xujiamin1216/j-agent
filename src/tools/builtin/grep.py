"""GrepTool -- search file contents by regex.

Walks a directory tree and searches file contents for a regex pattern.
Skips binary files and common unwanted directories (``.git``, ``__pycache__``,
``.venv``). Results are capped at 250 matches.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.tools.base import Tool

# Maximum number of matches to return.
MAX_MATCHES = 250

# Directories to skip during traversal.
_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".egg-info"}


class GrepTool(Tool):
    name = "grep"
    description = (
        "Search file contents for a regex pattern. Returns matching lines "
        "with file path and line number. Use 'include' to filter by file "
        "name glob (e.g. '*.py'). Returns up to 250 matches."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regular expression pattern to search for.",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in. Default: current directory.",
            },
            "include": {
                "type": "string",
                "description": "Glob pattern to filter file names (e.g. '*.py').",
            },
        },
        "required": ["pattern"],
        "additionalProperties": False,
    }

    def execute(
        self,
        *,
        pattern: str,
        path: str | None = None,
        include: str | None = None,
        **kwargs: Any,
    ) -> str:
        regex = re.compile(pattern)
        base = self._resolve_path(path)

        if not base.exists():
            raise FileNotFoundError(f"路径不存在: {path}")

        # Determine the set of files to search.
        if base.is_file():
            files = [base]
        else:
            files = [
                p
                for p in base.rglob("*")
                if p.is_file()
                and not any(part in _SKIP_DIRS for part in p.parts)
            ]
            if include:
                files = [p for p in files if p.match(include)]

        matches: list[str] = []
        total_matches = 0

        for filepath in files:
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            except (OSError, UnicodeDecodeError):
                continue

            for lineno, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    total_matches += 1
                    if len(matches) < MAX_MATCHES:
                        # Truncate very long lines for readability.
                        display = line if len(line) <= 200 else line[:200] + "..."
                        matches.append(f"{filepath}:{lineno}: {display}")

        if not matches:
            return f"未找到匹配 '{pattern}' 的内容。"

        result = "\n".join(matches)

        if total_matches > MAX_MATCHES:
            result += (
                f"\n\n... [共 {total_matches} 条匹配, "
                f"仅显示前 {MAX_MATCHES} 条]"
            )

        return result
