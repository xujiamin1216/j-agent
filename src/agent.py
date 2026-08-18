"""Core agent loop -- the heart of the harness.

The agent loop orchestrates the interaction between the user, the LLM,
and the tools. It is the central harness that ties everything together:

    user input -> LLM -> (tool calls -> tool execution -> LLM)* -> output

The loop continues calling the LLM as long as the LLM requests tool
calls, up to a maximum iteration limit to prevent runaway loops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from src.config import Config
from src.llm.base import LLMProvider
from src.llm.types import Message, ToolCall, ToolResult
from src.planning.plan import Plan
from src.tools.base import ToolRegistry

if TYPE_CHECKING:
    from src.memory.context_manager import ContextManager
    from src.permission.manager import PermissionManager

# Maximum consecutive LLM calls for a single user turn. Prevents infinite
# tool-call loops if the LLM keeps requesting tools without finishing.
MAX_ITERATIONS = 20

# Callback type for streaming agent events to the UI layer.
EventCallback = Callable[[str, dict], None]


class Agent:
    """The main agent that drives the conversation loop."""

    def __init__(
        self,
        config: Config,
        provider: LLMProvider,
        tools: ToolRegistry | None = None,
        on_event: EventCallback | None = None,
        context_manager: ContextManager | None = None,
        permission_manager: PermissionManager | None = None,
        plan: Plan | None = None,
    ) -> None:
        self._config = config
        self._provider = provider
        self._tools = tools or ToolRegistry()
        self._messages: list[Message] = []
        self._on_event = on_event or _noop_callback
        self._context_manager = context_manager
        self._permission_manager = permission_manager
        self._plan = plan or Plan()

    @property
    def tools(self) -> ToolRegistry:
        return self._tools

    @property
    def messages(self) -> list[Message]:
        return self._messages

    @property
    def permission_manager(self) -> PermissionManager | None:
        return self._permission_manager

    @property
    def plan(self) -> Plan:
        return self._plan

    def run(self, user_input: str) -> str:
        """Process one user turn and return the assistant's text response.

        This is the main entry point. It adds the user message to history,
        then loops: call LLM -> execute tools -> call LLM again, until the
        LLM produces a final text response with no tool calls.
        """
        self._messages.append(Message.user(user_input))

        tool_specs = self._tools.to_specs() or None

        for iteration in range(MAX_ITERATIONS):
            # Manage context window before each LLM call.
            if self._context_manager:
                info = self._context_manager.manage(self._messages)
                if info:
                    self._on_event("context_managed", info)

            response = self._provider.chat(
                messages=self._messages,
                tools=tool_specs,
                system=self._config.system_prompt,
            )
            self._messages.append(response)

            # If the LLM didn't request any tools, we're done.
            if not response.tool_calls:
                self._on_event("assistant_response", {"content": response.content})
                return response.content

            # Execute each requested tool call.
            for tc in response.tool_calls:
                self._on_event(
                    "tool_call",
                    {"name": tc.name, "arguments": tc.arguments},
                )

                result = self._execute_tool(tc)

                self._on_event(
                    "tool_result",
                    {
                        "name": tc.name,
                        "content": result.content,
                        "is_error": result.is_error,
                    },
                )

                self._messages.append(
                    Message.tool(
                        tool_call_id=result.tool_call_id,
                        content=result.content,
                        is_error=result.is_error,
                    )
                )

        # Exhausted iterations without a final response.
        msg = f"Agent reached max iterations ({MAX_ITERATIONS}) without completing."
        self._on_event("max_iterations", {"message": msg})
        return msg

    def _execute_tool(self, tc: ToolCall) -> ToolResult:
        """Execute a tool call, gating it through the permission manager.

        If a permission manager is configured and denies the call, a
        ``permission_denied`` event is emitted and an ``is_error`` result is
        returned without executing the tool.
        """
        if self._permission_manager is not None:
            decision = self._permission_manager.check(tc.name, tc.arguments)
            if not decision.allowed:
                self._on_event(
                    "permission_denied",
                    {
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "risk_level": decision.risk_level,
                        "reason": decision.reason,
                    },
                )
                return ToolResult(
                    tool_call_id=tc.id,
                    content=f"[权限拒绝] {decision.reason}",
                    is_error=True,
                )

        result = self._tools.execute(tc.name, tc.arguments)
        # Attach the real tool_call_id to the result.
        return ToolResult(
            tool_call_id=tc.id,
            content=result.content,
            is_error=result.is_error,
        )


def _noop_callback(event: str, data: dict) -> None:
    """Default no-op event callback."""
    pass
