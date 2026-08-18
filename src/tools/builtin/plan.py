"""PlanTool -- create/update/view a task list for multi-step work.

The plan is a shared ``Plan`` object (also held by the Agent for session
persistence). The CLI injects the plan after discovery; standalone tools
fall back to their own empty plan.
"""

from __future__ import annotations

from typing import Any

from src.permission.risk import RiskLevel
from src.planning.plan import Plan
from src.tools.base import Tool


class PlanTool(Tool):
    name = "plan"
    risk_level = RiskLevel.SAFE
    description = (
        "Manage a task list for multi-step work. Use action 'create' to add "
        "a task (with 'title'), 'update' to change a task's status/title/"
        "description (status is one of pending/in_progress/completed), "
        "'list' to view all tasks, or 'get' to view one task by 'task_id'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Operation: 'create', 'update', 'list', or 'get'.",
            },
            "title": {
                "type": "string",
                "description": "Task title (for create/update).",
            },
            "task_id": {
                "type": "string",
                "description": "Task id (for update/get).",
            },
            "status": {
                "type": "string",
                "description": "Task status: 'pending', 'in_progress', or 'completed'.",
            },
            "description": {
                "type": "string",
                "description": "Optional task description.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def __init__(self, plan: Plan | None = None) -> None:
        self.plan = plan or Plan()

    def execute(
        self,
        *,
        action: str,
        title: str = "",
        task_id: str = "",
        status: str = "",
        description: str = "",
        **kwargs: Any,
    ) -> str:
        plan = self.plan

        if action == "create":
            if not title:
                raise ValueError("create 操作需要 title 参数")
            task = plan.add_task(title, description)
            return f"已创建任务 [{task.id}] {task.title}"

        if action == "update":
            if not task_id:
                raise ValueError("update 操作需要 task_id 参数")
            task = plan.update_task(
                task_id,
                status=status or None,
                title=title or None,
                description=description or None,
            )
            return f"已更新任务 [{task.id}] {task.title} -> {task.status}"

        if action == "list":
            tasks = plan.list_tasks()
            if not tasks:
                return "暂无任务。"
            lines = [f"  [{t.status}] [{t.id}] {t.title}" for t in tasks]
            return "任务列表:\n" + "\n".join(lines)

        if action == "get":
            if not task_id:
                raise ValueError("get 操作需要 task_id 参数")
            task = plan.get_task(task_id)
            result = f"[{task.status}] [{task.id}] {task.title}"
            if task.description:
                result += f"\n  {task.description}"
            return result

        raise ValueError(f"未知操作: {action} (支持: create, update, list, get)")
