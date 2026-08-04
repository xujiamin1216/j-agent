"""Tests for WorkContext -- working directory binding."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.work_context import WorkContext


class TestWorkContext:
    def test_from_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        ctx = WorkContext.from_cwd()
        assert ctx.work_dir == tmp_path.resolve()

    def test_data_dir(self, tmp_path: Path):
        ctx = WorkContext(work_dir=tmp_path)
        assert ctx.data_dir == tmp_path / ".j-agent"
        assert ctx.data_dir.exists()

    def test_memory_file(self, tmp_path: Path):
        ctx = WorkContext(work_dir=tmp_path)
        assert ctx.memory_file == tmp_path / ".j-agent" / "memory.json"

    def test_sessions_dir(self, tmp_path: Path):
        ctx = WorkContext(work_dir=tmp_path)
        assert ctx.sessions_dir == tmp_path / ".j-agent" / "sessions"
        assert ctx.sessions_dir.exists()

    def test_data_dir_created_on_access(self, tmp_path: Path):
        ctx = WorkContext(work_dir=tmp_path)
        # Directory should not exist until accessed.
        assert not (tmp_path / ".j-agent").exists()
        _ = ctx.data_dir
        assert (tmp_path / ".j-agent").exists()

    def test_different_work_dirs_isolated(self, tmp_path: Path):
        dir_a = tmp_path / "project-a"
        dir_b = tmp_path / "project-b"
        dir_a.mkdir()
        dir_b.mkdir()

        ctx_a = WorkContext(work_dir=dir_a)
        ctx_b = WorkContext(work_dir=dir_b)

        assert ctx_a.memory_file != ctx_b.memory_file
        assert ctx_a.sessions_dir != ctx_b.sessions_dir
