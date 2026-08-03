"""BashTool -- execute shell commands with timeout.

Runs a shell command via ``subprocess.run``, capturing stdout and stderr.
A configurable timeout (default 30 seconds) prevents runaway processes.
"""

from __future__ import annotations

import subprocess
from typing import Any

from src.tools.base import Tool


class BashTool(Tool):
    name = "bash"
    description = (
        "Execute a shell command and return stdout, stderr, and exit code. "
        "Use 'timeout' to set a max execution time in seconds (default 30). "
        "Use 'cwd' to set the working directory."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds. Default: 30.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command. Default: current directory.",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    def execute(
        self,
        *,
        command: str,
        timeout: int | None = None,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> str:
        time_limit = timeout or 30

        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=time_limit,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            return (
                f"[超时] 命令在 {time_limit} 秒后未完成, 已终止。\n"
                f"命令: {command}"
            )

        parts = [f"退出码: {proc.returncode}"]
        if proc.stdout:
            parts.append(f"stdout:\n{proc.stdout.rstrip()}")
        if proc.stderr:
            parts.append(f"stderr:\n{proc.stderr.rstrip()}")

        return "\n".join(parts)
