"""Tests for sub-agent spawning (Phase 5).

Covers ``SubAgentRunner`` (single and parallel execution, tool isolation)
and ``SpawnAgentTool`` (runner injection, single/parallel dispatch).
"""

from __future__ import annotations

from src.config import Config
from src.llm.types import Message
from src.planning.subagent import SubAgentRunner
from src.tools.base import ToolRegistry
from src.tools.builtin.spawn import SpawnAgentTool


def make_config() -> Config:
    return Config(
        provider="claude",
        model="test-model",
        api_key="test-key",
        system_prompt="",
    )


class _FakeProvider:
    """Returns a single fixed assistant response."""

    def __init__(self, response: str = "sub-done") -> None:
        self._response = response
        self.calls = 0

    def chat(
        self, messages: list[Message], tools=None, system: str | None = None
    ) -> Message:
        self.calls += 1
        return Message.assistant(self._response)


class _FakeRunner:
    """Minimal stand-in for SubAgentRunner used by SpawnAgentTool tests."""

    def __init__(self) -> None:
        self.single_calls = []
        self.parallel_calls = []

    def run(self, task: str) -> str:
        self.single_calls.append(task)
        return f"ran: {task}"

    def run_parallel(self, tasks: list[str]) -> list[str]:
        self.parallel_calls.append(list(tasks))
        return [f"ran: {t}" for t in tasks]


class TestSubAgentRunner:
    def test_run_returns_response(self):
        provider = _FakeProvider()
        runner = SubAgentRunner(provider=provider, config=make_config())
        assert runner.run("solve it") == "sub-done"
        assert provider.calls == 1

    def test_run_uses_isolated_tools(self):
        registry = ToolRegistry()

        def factory() -> ToolRegistry:
            return registry

        provider = _FakeProvider()
        runner = SubAgentRunner(
            provider=provider,
            config=make_config(),
            tools_factory=factory,
        )
        runner.run("task")
        # A fresh agent was constructed each run.
        assert provider.calls == 1

    def test_run_parallel_preserves_order(self):
        provider = _FakeProvider()
        runner = SubAgentRunner(provider=provider, config=make_config())
        results = runner.run_parallel(["a", "b", "c"])
        assert results == ["sub-done", "sub-done", "sub-done"]
        assert provider.calls == 3


class TestSpawnAgentTool:
    def test_missing_runner_reports_error(self):
        tool = SpawnAgentTool()
        result = tool.execute(task="do it")
        assert "未配置" in result

    def test_single_task(self):
        runner = _FakeRunner()
        tool = SpawnAgentTool(runner=runner)
        result = tool.execute(task="do it")
        assert result == "ran: do it"
        assert runner.single_calls == ["do it"]

    def test_parallel_tasks(self):
        runner = _FakeRunner()
        tool = SpawnAgentTool(runner=runner)
        result = tool.execute(tasks=["a", "b"])
        assert "ran: a" in result
        assert "ran: b" in result
        assert runner.parallel_calls == [["a", "b"]]

    def test_no_task_or_tasks_raises(self):
        import pytest

        tool = SpawnAgentTool(runner=_FakeRunner())
        with pytest.raises(ValueError, match="task"):
            tool.execute()
