"""Task planning -- a persistent, session-scoped task list.

Phase 5. ``Plan`` holds an ordered list of ``Task`` objects with
create/read/update operations and JSON serialization. A plan is associated
with a conversation session and persisted alongside it (see
``Session.plan``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


class TaskStatus:
    """Valid task statuses."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

    ALL = (PENDING, IN_PROGRESS, COMPLETED)


@dataclass
class Task:
    """A single task within a plan."""

    id: str
    title: str
    status: str = TaskStatus.PENDING
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Task:
        return cls(
            id=d["id"],
            title=d["title"],
            status=d.get("status", TaskStatus.PENDING),
            description=d.get("description", ""),
        )


@dataclass
class Plan:
    """An ordered task list with persistence hooks."""

    tasks: list[Task] = field(default_factory=list)

    def add_task(self, title: str, description: str = "") -> Task:
        """Append a new task and return it."""
        task = Task(id=_new_task_id(), title=title, description=description)
        self.tasks.append(task)
        return task

    def get_task(self, task_id: str) -> Task:
        """Look up a task by id. Raises KeyError if not found."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"未找到任务: {task_id}")

    def update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> Task:
        """Update a task's fields. Only non-None fields are changed."""
        task = self.get_task(task_id)
        if status is not None:
            if status not in TaskStatus.ALL:
                raise ValueError(f"无效状态: {status}")
            task.status = status
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        return task

    def list_tasks(self) -> list[Task]:
        """Return a copy of the task list."""
        return list(self.tasks)

    def replace(self, other: Plan) -> None:
        """Replace this plan's tasks in-place (preserves object identity).

        Used when restoring a plan from a loaded session, so that any
        reference held by a tool remains valid.
        """
        self.tasks = list(other.tasks)

    def to_dict(self) -> dict[str, Any]:
        return {"tasks": [t.to_dict() for t in self.tasks]}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Plan:
        if not d:
            return cls()
        return cls(tasks=[Task.from_dict(t) for t in d.get("tasks", [])])


def _new_task_id() -> str:
    """Generate a short unique task id."""
    return uuid.uuid4().hex[:8]
