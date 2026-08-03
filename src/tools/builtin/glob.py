"""GlobTool -- find files by glob pattern.

Uses ``pathlib.Path.glob()`` to find files matching a pattern. Supports
``**`` for recursive matching. Results are sorted by modification time
(newest first) and capped at 100 entries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.tools.base import Tool

# Maximum number of results to return.
MAX_RESULTS = 100


class GlobTool(Tool):
    name = "glob"
    description = (
        "Find files matching a glob pattern. Supports '**' for recursive "
        "matching. Returns up to 100 results sorted by modification time "
        "(newest first)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern (e.g. '**/*.py', 'src/*.ts').",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in. Default: current directory.",
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
        **kwargs: Any,
    ) -> str:
        base = Path(path or ".")
        if not base.exists():
            raise FileNotFoundError(f"路径不存在: {path}")

        matches = list(base.glob(pattern))
        # Filter to files only (skip directories).
        files = [m for m in matches if m.is_file()]

        if not files:
            return f"未找到匹配 '{pattern}' 的文件。"

        # Sort by modification time, newest first.
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        total = len(files)
        capped = files[:MAX_RESULTS]

        lines = [str(f) for f in capped]
        result = "\n".join(lines)

        if total > MAX_RESULTS:
            result += f"\n\n... [共 {total} 条匹配, 仅显示前 {MAX_RESULTS} 条]"

        return result
