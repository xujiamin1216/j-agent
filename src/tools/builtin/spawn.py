"""SpawnAgentTool -- run independent sub-agents for sub-tasks.

Sub-agents have isolated message history and their own tool registry (the
CLI's factory omits this tool to prevent unbounded nesting). Multiple tasks
can be run in parallel. The runner is injected by the CLI; without it the
tool reports an error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.permission.risk import RiskLevel
from src.tools.base import Tool

if TYPE_CHECKING:
    from src.planning.subagent import SubAgentRunner


class SpawnAgentTool(Tool):
    name = "spawn_agent"
    risk_level = RiskLevel.CONFIRM
    description = (
        "Spawn one or more sub-agents to work on sub-tasks in isolation and "
        "return their results. Use 'task' for a single sub-task or 'tasks' "
        "for multiple sub-tasks (run in parallel). Each sub-agent runs with "
        "its own independent context."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "A single sub-task description.",
            },
            "tasks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Multiple sub-task descriptions (run in parallel).",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, runner: SubAgentRunner | None = None) -> None:
        self.runner = runner

    def execute(
        self,
        *,
        task: str = "",
        tasks: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        if self.runner is None:
            return "[错误] 子 Agent 运行器未配置"

        if tasks:
            results = self.runner.run_parallel(list(tasks))
            lines = [f"### 子任务 {i + 1}\n{r}" for i, r in enumerate(results)]
            return "\n\n".join(lines)

        if task:
            return self.runner.run(task)

        raise ValueError("需要 task 或 tasks 参数")
