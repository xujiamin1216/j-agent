"""Tool base class and registry.

The tool framework provides a uniform interface for defining, registering,
and executing tools. Tools are the primary way the LLM interacts with the
world -- they are the "hands" of the agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from src.llm.types import ToolResult, ToolSpec
from src.permission.risk import RiskLevel
from src.tools.validation import ValidationError, validate_arguments

# Maximum characters of tool output before truncation kicks in.
MAX_OUTPUT_CHARS = 30_000


class Tool(ABC):
    """Base class for all agent tools.

    Subclasses must define:
        name:        A unique identifier for the tool.
        description: A human-readable description sent to the LLM.
        parameters:  JSON Schema describing accepted arguments.
        execute():   The actual tool logic.
    """

    name: str
    description: str
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    # Static risk level for permission gating (Phase 4). Subclasses that
    # mutate state or execute code should override this to
    # ``RiskLevel.CONFIRM`` (or ``RiskLevel.DANGEROUS``).
    risk_level: str = RiskLevel.SAFE

    # Working directory for path resolution. Set by ToolRegistry.
    work_dir: Path | None = None

    def _resolve_path(self, path: str | None = None) -> Path:
        """Resolve a path relative to the working directory.

        Absolute paths are returned as-is. If *path* is None, the
        working directory itself is returned.
        """
        base = self.work_dir or Path.cwd()
        if path is None:
            return base
        p = Path(path)
        return p if p.is_absolute() else base / p

    def _resolve_work_path(self, path: str) -> Path:
        """Resolve *path* and enforce that it stays within the working directory.

        File tools use this to sandbox access to the bound work directory.
        The check only applies when a ``work_dir`` is bound (the normal CLI
        case); standalone tools without a work directory are unrestricted.

        Raises PermissionError if the resolved path escapes the work directory.
        """
        resolved = self._resolve_path(path)
        if self.work_dir is None:
            return resolved
        base = self.work_dir.resolve()
        if not resolved.resolve().is_relative_to(base):
            raise PermissionError(f"路径超出工作目录范围: {path}")
        return resolved

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Run the tool with validated arguments. Returns output as a string."""
        ...

    def to_spec(self) -> ToolSpec:
        """Convert to a ToolSpec for sending to the LLM."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )


class ToolRegistry:
    """Manages tool registration, lookup, and execution."""

    def __init__(self, work_dir: Path | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._work_dir = work_dir

    def register(self, tool: Tool) -> None:
        """Register a tool. Raises ValueError if name is already taken."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        if self._work_dir is not None:
            tool.work_dir = self._work_dir
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool by name, catching exceptions.

        Before execution, arguments are validated against the tool's JSON
        Schema. After execution, output exceeding ``MAX_OUTPUT_CHARS`` is
        truncated with a trailing notice.

        Returns a ToolResult with is_error=True if the tool is unknown,
        if validation fails, or if the tool raises an exception.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                tool_call_id="",
                content=f"Unknown tool: {name}",
                is_error=True,
            )

        try:
            validate_arguments(tool.parameters, arguments)
        except ValidationError as e:
            return ToolResult(
                tool_call_id="",
                content=f"参数校验失败: {e}",
                is_error=True,
            )

        try:
            result = tool.execute(**arguments)
            return ToolResult(
                tool_call_id="",
                content=_truncate(result),
                is_error=False,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"{type(e).__name__}: {e}",
                is_error=True,
            )

    def to_specs(self) -> list[ToolSpec]:
        """Get ToolSpecs for all registered tools."""
        return [tool.to_spec() for tool in self._tools.values()]

    def names(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def risk_levels(self) -> dict[str, str]:
        """Map each registered tool name to its static risk level."""
        return {name: tool.risk_level for name, tool in self._tools.items()}


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Truncate *text* to *limit* characters, appending a notice if cut."""
    if len(text) <= limit:
        return text
    return (
        text[:limit]
        + f"\n\n... [输出已截断: 原始 {len(text)} 字符, "
        f"截断至 {limit} 字符]"
    )
