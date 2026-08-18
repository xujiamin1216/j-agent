"""Sub-agent spawning -- run independent sub-agents for sub-tasks.

Phase 5. ``SubAgentRunner`` creates fresh ``Agent`` instances with isolated
message history and runs them on a sub-task, optionally in parallel. The
runner is constructed by the CLI with the shared provider/config and a
tools factory; each sub-agent gets its own ``ToolRegistry``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Callable

from src.tools.base import ToolRegistry

if TYPE_CHECKING:
    from src.agent import Agent
    from src.config import Config
    from src.llm.base import LLMProvider
    from src.permission.manager import PermissionManager


class SubAgentRunner:
    """Creates and runs sub-agents for isolated sub-tasks."""

    def __init__(
        self,
        provider: LLMProvider,
        config: Config,
        tools_factory: Callable[[], ToolRegistry] | None = None,
        permission_manager: PermissionManager | None = None,
    ) -> None:
        self._provider = provider
        self._config = config
        self._tools_factory = tools_factory
        self._permission_manager = permission_manager

    def run(self, task: str) -> str:
        """Run a single sub-agent on *task* and return its text response."""
        return self._make_agent().run(task)

    def run_parallel(self, tasks: list[str]) -> list[str]:
        """Run one sub-agent per task concurrently, preserving order."""
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            return list(executor.map(self.run, tasks))

    def _make_agent(self) -> Agent:
        from src.agent import Agent

        tools = self._tools_factory() if self._tools_factory else ToolRegistry()
        return Agent(
            config=self._config,
            provider=self._provider,
            tools=tools,
            permission_manager=self._permission_manager,
        )
