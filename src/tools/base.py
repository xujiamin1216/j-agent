"""Tool base class and registry.

The tool framework provides a uniform interface for defining, registering,
and executing tools. Tools are the primary way the LLM interacts with the
world -- they are the "hands" of the agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.llm.types import ToolResult, ToolSpec
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

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool. Raises ValueError if name is already taken."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
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


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Truncate *text* to *limit* characters, appending a notice if cut."""
    if len(text) <= limit:
        return text
    return (
        text[:limit]
        + f"\n\n... [输出已截断: 原始 {len(text)} 字符, "
        f"截断至 {limit} 字符]"
    )
