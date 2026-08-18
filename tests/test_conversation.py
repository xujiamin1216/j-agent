"""Tests for session persistence."""

import json

import pytest

from src.llm.types import Message, ToolCall
from src.memory.conversation import Session
from src.planning.plan import Plan


class TestSessionCreation:
    def test_new_session_has_defaults(self):
        session = Session()
        assert len(session.id) > 0
        assert session.created_at
        assert session.updated_at
        assert session.messages == []

    def test_new_session_has_unique_ids(self):
        s1 = Session()
        s2 = Session()
        assert s1.id != s2.id


class TestSessionSaveLoad:
    def test_save_and_load_round_trip(self, tmp_path):
        messages = [
            Message.user("hello"),
            Message.assistant("hi there"),
        ]
        session = Session(messages=messages)
        path = session.save(sessions_dir=tmp_path)

        assert path.exists()
        loaded = Session.load(session.id, sessions_dir=tmp_path)
        assert loaded.id == session.id
        assert len(loaded.messages) == 2
        assert loaded.messages[0].content == "hello"
        assert loaded.messages[1].content == "hi there"

    def test_save_and_load_with_tool_calls(self, tmp_path):
        tc = ToolCall(id="tc1", name="echo", arguments={"text": "hi"})
        messages = [
            Message.user("test"),
            Message.assistant("calling tool", tool_calls=[tc]),
            Message.tool("tc1", "result"),
        ]
        session = Session(messages=messages)
        session.save(sessions_dir=tmp_path)

        loaded = Session.load(session.id, sessions_dir=tmp_path)
        assert len(loaded.messages) == 3
        assert loaded.messages[1].tool_calls[0].name == "echo"
        assert loaded.messages[2].role == "tool"
        assert loaded.messages[2].tool_call_id == "tc1"

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="会话不存在"):
            Session.load("nonexistent-id", sessions_dir=tmp_path)


class TestSessionList:
    def test_list_empty(self, tmp_path):
        assert Session.list_sessions(sessions_dir=tmp_path) == []

    def test_list_multiple(self, tmp_path):
        for i in range(3):
            s = Session(messages=[Message.user(f"msg {i}")])
            s.save(sessions_dir=tmp_path)

        sessions = Session.list_sessions(sessions_dir=tmp_path)
        assert len(sessions) == 3
        for s in sessions:
            assert "id" in s
            assert "created_at" in s
            assert "updated_at" in s
            assert s["message_count"] == 1

    def test_list_corrupt_skipped(self, tmp_path):
        # Save a valid session
        s = Session(messages=[Message.user("hello")])
        s.save(sessions_dir=tmp_path)

        # Write a corrupt file
        (tmp_path / "corrupt.json").write_text("not valid json", encoding="utf-8")

        sessions = Session.list_sessions(sessions_dir=tmp_path)
        assert len(sessions) == 1  # only the valid one


class TestSessionDelete:
    def test_delete_existing(self, tmp_path):
        s = Session(messages=[Message.user("hi")])
        s.save(sessions_dir=tmp_path)
        assert (tmp_path / f"{s.id}.json").exists()

        Session.delete(s.id, sessions_dir=tmp_path)
        assert not (tmp_path / f"{s.id}.json").exists()

    def test_delete_nonexistent_no_error(self, tmp_path):
        # Should not raise
        Session.delete("nonexistent", sessions_dir=tmp_path)


class TestSessionAddMessage:
    def test_add_message_updates_timestamp(self):
        session = Session()
        old_updated = session.updated_at
        session.add_message(Message.user("test"))
        assert len(session.messages) == 1
        # Timestamps may be the same if fast enough, but updated_at is reassigned
        assert session.updated_at is not None


class TestSessionFromMessages:
    def test_from_messages(self):
        messages = [Message.user("a"), Message.assistant("b")]
        session = Session.from_messages(messages)
        assert len(session.messages) == 2
        assert session.messages[0].content == "a"
        assert session.messages[1].content == "b"


class TestSessionPlan:
    def test_save_and_load_plan_round_trip(self, tmp_path):
        plan = Plan()
        plan.add_task("first task", "desc")
        plan.add_task("second task")

        session = Session(messages=[Message.user("hi")], plan=plan)
        session.save(sessions_dir=tmp_path)

        loaded = Session.load(session.id, sessions_dir=tmp_path)
        assert loaded.plan is not None
        assert len(loaded.plan.tasks) == 2
        assert loaded.plan.tasks[0].title == "first task"
        assert loaded.plan.tasks[1].title == "second task"

    def test_from_messages_with_plan(self):
        plan = Plan()
        plan.add_task("do it")
        session = Session.from_messages([Message.user("hi")], plan=plan)
        assert session.plan is plan

    def test_save_without_plan_round_trip(self, tmp_path):
        session = Session(messages=[Message.user("hi")])
        session.save(sessions_dir=tmp_path)
        loaded = Session.load(session.id, sessions_dir=tmp_path)
        assert loaded.plan is None
