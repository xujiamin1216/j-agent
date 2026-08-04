"""MemoryTool -- save and retrieve persistent information across sessions.

The agent can use this tool to proactively remember key facts, decisions,
or context that should persist beyond the current conversation. Data is
stored in ``<work_dir>/.j-agent/memory.json`` via MemoryStore when a
work_dir is bound, otherwise in ``~/.j-agent/memory.json``.
"""

from __future__ import annotations

from typing import Any

from src.memory.memory_store import MemoryStore
from src.tools.base import Tool


class MemoryTool(Tool):
    name = "memory"
    description = (
        "Save or retrieve persistent information that persists across conversations. "
        "Use action 'save' with key and value to store, 'read' with key to retrieve, "
        "'list' to see all keys, or 'delete' with key to remove."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Operation: 'save', 'read', 'list', or 'delete'.",
            },
            "key": {
                "type": "string",
                "description": "Memory key (required for save/read/delete).",
            },
            "value": {
                "type": "string",
                "description": "Value to store (required for save action).",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def __init__(self) -> None:
        self._store: MemoryStore | None = None

    def _get_store(self) -> MemoryStore:
        """Lazily create a MemoryStore, scoped to work_dir if bound."""
        if self._store is None:
            if self.work_dir is not None:
                from src.work_context import WorkContext

                self._store = MemoryStore(
                    memory_file=WorkContext(self.work_dir).memory_file
                )
            else:
                self._store = MemoryStore()
        return self._store

    def execute(
        self,
        *,
        action: str,
        key: str = "",
        value: str = "",
        **kwargs: Any,
    ) -> str:
        store = self._get_store()

        if action == "save":
            if not key:
                raise ValueError("save 操作需要 key 参数")
            if not value:
                raise ValueError("save 操作需要 value 参数")
            return store.save(key, value)

        if action == "read":
            if not key:
                raise ValueError("read 操作需要 key 参数")
            return store.read(key)

        if action == "list":
            keys = store.list_keys()
            if not keys:
                return "暂无存储的记忆。"
            return "已存储的记忆:\n" + "\n".join(f"  - {k}" for k in keys)

        if action == "delete":
            if not key:
                raise ValueError("delete 操作需要 key 参数")
            return store.delete(key)

        raise ValueError(f"未知操作: {action} (支持: save, read, list, delete)")
