"""Tests for the planning system (Phase 5).

Covers ``Task`` and ``Plan`` CRUD, JSON serialization, and the in-place
``Plan.replace`` used when restoring a plan from a saved session.
"""

from __future__ import annotations

import pytest

from src.planning.plan import Plan, Task, TaskStatus


class TestTask:
    def test_defaults(self):
        task = Task(id="abc", title="do the thing")
        assert task.status == TaskStatus.PENDING
        assert task.description == ""

    def test_to_dict(self):
        task = Task(id="abc", title="do the thing", status=TaskStatus.IN_PROGRESS)
        assert task.to_dict() == {
            "id": "abc",
            "title": "do the thing",
            "status": "in_progress",
            "description": "",
        }

    def test_from_dict(self):
        task = Task.from_dict(
            {"id": "abc", "title": "t", "status": "completed", "description": "d"}
        )
        assert task.id == "abc"
        assert task.status == "completed"
        assert task.description == "d"

    def test_from_dict_missing_status_defaults(self):
        task = Task.from_dict({"id": "abc", "title": "t"})
        assert task.status == TaskStatus.PENDING
        assert task.description == ""


class TestPlanCrud:
    def test_add_task(self):
        plan = Plan()
        task = plan.add_task("write tests", "for phase 5")
        assert task.id
        assert task.title == "write tests"
        assert task.status == TaskStatus.PENDING
        assert len(plan.tasks) == 1

    def test_add_task_unique_ids(self):
        plan = Plan()
        t1 = plan.add_task("a")
        t2 = plan.add_task("b")
        assert t1.id != t2.id

    def test_get_task(self):
        plan = Plan()
        task = plan.add_task("lookup")
        assert plan.get_task(task.id) is task

    def test_get_task_missing_raises(self):
        plan = Plan()
        with pytest.raises(KeyError):
            plan.get_task("nope")

    def test_update_task_status(self):
        plan = Plan()
        task = plan.add_task("t")
        updated = plan.update_task(task.id, status="completed")
        assert updated.status == "completed"
        assert plan.get_task(task.id).status == "completed"

    def test_update_task_fields(self):
        plan = Plan()
        task = plan.add_task("old title")
        plan.update_task(task.id, title="new title", description="desc")
        assert task.title == "new title"
        assert task.description == "desc"

    def test_update_task_invalid_status_raises(self):
        plan = Plan()
        task = plan.add_task("t")
        with pytest.raises(ValueError, match="无效状态"):
            plan.update_task(task.id, status="bogus")

    def test_list_tasks_returns_copy(self):
        plan = Plan()
        plan.add_task("a")
        tasks = plan.list_tasks()
        tasks.clear()
        assert len(plan.tasks) == 1


class TestPlanSerialization:
    def test_round_trip(self):
        plan = Plan()
        plan.add_task("first", "desc 1")
        plan.add_task("second")
        plan.update_task(plan.tasks[0].id, status="in_progress")

        restored = Plan.from_dict(plan.to_dict())
        assert len(restored.tasks) == 2
        assert restored.tasks[0].title == "first"
        assert restored.tasks[0].status == "in_progress"
        assert restored.tasks[1].title == "second"

    def test_from_dict_none(self):
        assert Plan.from_dict(None).tasks == []


class TestPlanReplace:
    def test_replace_preserves_identity(self):
        plan = Plan()
        plan.add_task("original")

        other = Plan()
        other.add_task("restored")

        plan.replace(other)
        assert len(plan.tasks) == 1
        assert plan.tasks[0].title == "restored"
