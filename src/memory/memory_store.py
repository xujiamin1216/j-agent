"""Cross-session persistent key-value memory store.

Stored as a single JSON file at ``~/.j-agent/memory.json``. This allows
the agent to proactively save and retrieve key information across
conversations via the MemoryTool.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.config import create_data_dir


def _memory_file() -> Path:
    """Return the path to the persistent memory file."""
    return create_data_dir() / "memory.json"


class MemoryStore:
    """Cross-session persistent key-value memory store.

    Data is stored as a JSON object (dict[str, str]) in ~/.j-agent/memory.json.
    Corrupt files are treated as empty (graceful degradation).
    """

    def __init__(self, memory_file: Path | None = None) -> None:
        self._path = memory_file or _memory_file()
        self._data: dict[str, str] = self._load()

    def save(self, key: str, value: str) -> str:
        """Store a key-value pair. Overwrites if key exists."""
        self._data[key] = value
        self._persist()
        return f"已保存记忆: {key}"

    def read(self, key: str) -> str:
        """Retrieve a value by key."""
        if key not in self._data:
            raise KeyError(f"未找到记忆: {key}")
        return self._data[key]

    def list_keys(self) -> list[str]:
        """Return all stored keys."""
        return list(self._data.keys())

    def delete(self, key: str) -> str:
        """Delete a key-value pair."""
        if key not in self._data:
            raise KeyError(f"未找到记忆: {key}")
        del self._data[key]
        self._persist()
        return f"已删除记忆: {key}"

    def _load(self) -> dict[str, str]:
        """Load data from the JSON file."""
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _persist(self) -> None:
        """Write data to the JSON file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
