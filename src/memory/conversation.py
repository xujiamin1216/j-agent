"""Session persistence -- save/load conversation history to disk.

Sessions are stored as JSON files in ``~/.j-agent/sessions/``. Each file
contains the session ID, timestamps, and the full message list. This
allows the user to resume previous conversations or review past sessions.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import create_data_dir
from src.llm.types import Message
from src.planning.plan import Plan


def _sessions_dir() -> Path:
    """Return the sessions directory, creating it if needed."""
    path = create_data_dir() / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Session:
    """A persistent conversation session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    messages: list[Message] = field(default_factory=list)
    plan: Plan | None = None

    def add_message(self, msg: Message) -> None:
        """Append a message and update the timestamp."""
        self.messages.append(msg)
        self.updated_at = datetime.now().isoformat()

    def save(self, sessions_dir: Path | None = None) -> Path:
        """Save session to a JSON file. Returns the file path."""
        directory = sessions_dir or _sessions_dir()
        directory.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now().isoformat()
        path = directory / f"{self.id}.json"
        data: dict[str, Any] = {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
            "plan": self.plan.to_dict() if self.plan is not None else None,
        }
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, session_id: str, sessions_dir: Path | None = None) -> Session:
        """Load a session from a JSON file."""
        directory = sessions_dir or _sessions_dir()
        path = directory / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"会话不存在: {session_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        messages = [Message.from_dict(m) for m in data.get("messages", [])]
        plan = Plan.from_dict(data.get("plan")) if data.get("plan") else None
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            messages=messages,
            plan=plan,
        )

    @staticmethod
    def list_sessions(sessions_dir: Path | None = None) -> list[dict[str, Any]]:
        """List all saved sessions.

        Returns a list of dicts with keys: id, created_at, updated_at, message_count.
        Corrupt files are silently skipped.
        """
        directory = sessions_dir or _sessions_dir()
        if not directory.exists():
            return []
        sessions: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append(
                    {
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "updated_at": data["updated_at"],
                        "message_count": len(data.get("messages", [])),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    @staticmethod
    def delete(session_id: str, sessions_dir: Path | None = None) -> None:
        """Delete a session file. No error if the file doesn't exist."""
        directory = sessions_dir or _sessions_dir()
        path = directory / f"{session_id}.json"
        if path.exists():
            path.unlink()

    @classmethod
    def from_messages(cls, messages: list[Message], plan: Plan | None = None) -> Session:
        """Create a new session from an existing message list."""
        return cls(messages=list(messages), plan=plan)
