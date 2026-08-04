"""Tests for the persistent memory store."""

import json

import pytest

from src.memory.memory_store import MemoryStore


class TestMemoryStoreCRUD:
    def test_save_and_read(self, tmp_path):
        store = MemoryStore(memory_file=tmp_path / "memory.json")
        result = store.save("name", "j-agent")
        assert "已保存" in result
        assert store.read("name") == "j-agent"

    def test_save_overwrites(self, tmp_path):
        store = MemoryStore(memory_file=tmp_path / "memory.json")
        store.save("key", "old")
        store.save("key", "new")
        assert store.read("key") == "new"

    def test_read_nonexistent_raises(self, tmp_path):
        store = MemoryStore(memory_file=tmp_path / "memory.json")
        with pytest.raises(KeyError, match="未找到记忆"):
            store.read("nonexistent")

    def test_list_keys_empty(self, tmp_path):
        store = MemoryStore(memory_file=tmp_path / "memory.json")
        assert store.list_keys() == []

    def test_list_keys_multiple(self, tmp_path):
        store = MemoryStore(memory_file=tmp_path / "memory.json")
        store.save("a", "1")
        store.save("b", "2")
        store.save("c", "3")
        assert len(store.list_keys()) == 3
        assert set(store.list_keys()) == {"a", "b", "c"}

    def test_delete_existing(self, tmp_path):
        store = MemoryStore(memory_file=tmp_path / "memory.json")
        store.save("key", "value")
        result = store.delete("key")
        assert "已删除" in result
        assert "key" not in store.list_keys()

    def test_delete_nonexistent_raises(self, tmp_path):
        store = MemoryStore(memory_file=tmp_path / "memory.json")
        with pytest.raises(KeyError, match="未找到记忆"):
            store.delete("nonexistent")


class TestMemoryStorePersistence:
    def test_persistence_across_instances(self, tmp_path):
        path = tmp_path / "memory.json"
        store1 = MemoryStore(memory_file=path)
        store1.save("key", "value")

        store2 = MemoryStore(memory_file=path)
        assert store2.read("key") == "value"

    def test_load_corrupt_file(self, tmp_path):
        path = tmp_path / "memory.json"
        path.write_text("not valid json", encoding="utf-8")
        store = MemoryStore(memory_file=path)
        assert store.list_keys() == []

    def test_load_missing_file(self, tmp_path):
        store = MemoryStore(memory_file=tmp_path / "nonexistent.json")
        assert store.list_keys() == []

    def test_file_is_valid_json(self, tmp_path):
        path = tmp_path / "memory.json"
        store = MemoryStore(memory_file=path)
        store.save("key", "value")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"key": "value"}
