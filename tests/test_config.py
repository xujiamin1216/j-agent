"""Tests for Config and work context loading (AGENT.md, .j-agent.env)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.config import CONFIG_FILE, CONTEXT_FILE, Config, load_work_context


@pytest.fixture
def temp_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Change cwd to a temp directory and return it."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all J_AGENT_ env vars to avoid interference."""
    for key in list(os.environ):
        if key.startswith("J_AGENT_"):
            monkeypatch.delenv(key, raising=False)


class TestLoadWorkContext:
    def test_returns_empty_when_no_file(self, temp_cwd: Path):
        assert load_work_context() == ""

    def test_returns_content_when_file_exists(self, temp_cwd: Path):
        (temp_cwd / CONTEXT_FILE).write_text("# My Project\nSome context.", encoding="utf-8")
        result = load_work_context()
        assert "# My Project" in result
        assert "Some context." in result

    def test_returns_empty_when_file_empty(self, temp_cwd: Path):
        (temp_cwd / CONTEXT_FILE).write_text("", encoding="utf-8")
        assert load_work_context() == ""

    def test_returns_empty_when_file_whitespace_only(self, temp_cwd: Path):
        (temp_cwd / CONTEXT_FILE).write_text("   \n\n  \n", encoding="utf-8")
        assert load_work_context() == ""


class TestConfigFromEnvWithContext:
    def test_context_appended_to_system_prompt(
        self, temp_cwd: Path, clean_env: None, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("J_AGENT_PROVIDER", "claude")
        monkeypatch.setenv("J_AGENT_API_KEY", "test-key")
        (temp_cwd / CONTEXT_FILE).write_text(
            "# Project Rules\nAlways use type hints.", encoding="utf-8"
        )

        config = Config.from_env()

        assert "# Project Rules" in config.system_prompt
        assert "Always use type hints." in config.system_prompt
        assert "工作上下文" in config.system_prompt

    def test_no_context_when_file_missing(
        self, temp_cwd: Path, clean_env: None, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("J_AGENT_PROVIDER", "claude")
        monkeypatch.setenv("J_AGENT_API_KEY", "test-key")

        config = Config.from_env()

        assert "工作上下文" not in config.system_prompt

    def test_no_context_when_file_empty(
        self, temp_cwd: Path, clean_env: None, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("J_AGENT_PROVIDER", "claude")
        monkeypatch.setenv("J_AGENT_API_KEY", "test-key")
        (temp_cwd / CONTEXT_FILE).write_text("", encoding="utf-8")

        config = Config.from_env()

        assert "工作上下文" not in config.system_prompt

    def test_custom_prompt_plus_context(
        self, temp_cwd: Path, clean_env: None, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("J_AGENT_PROVIDER", "claude")
        monkeypatch.setenv("J_AGENT_API_KEY", "test-key")
        monkeypatch.setenv("J_AGENT_SYSTEM_PROMPT", "You are a coding expert.")
        (temp_cwd / CONTEXT_FILE).write_text("Project: j-agent", encoding="utf-8")

        config = Config.from_env()

        assert config.system_prompt.startswith("You are a coding expert.")
        assert "Project: j-agent" in config.system_prompt
        assert "---" in config.system_prompt


class TestConfigFromEnvWithOverride:
    def test_j_agent_env_overrides_env(
        self, temp_cwd: Path, clean_env: None, monkeypatch: pytest.MonkeyPatch
    ):
        """.j-agent.env overrides .env values."""
        monkeypatch.setenv("J_AGENT_PROVIDER", "claude")
        monkeypatch.setenv("J_AGENT_API_KEY", "test-key")
        # .env sets model to one value
        (temp_cwd / ".env").write_text("J_AGENT_MODEL=gpt-4o\n", encoding="utf-8")
        # .j-agent.env overrides it
        (temp_cwd / CONFIG_FILE).write_text("J_AGENT_MODEL=gpt-4o-mini\n", encoding="utf-8")

        config = Config.from_env()

        assert config.model == "gpt-4o-mini"

    def test_j_agent_env_overrides_system_prompt(
        self, temp_cwd: Path, clean_env: None, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("J_AGENT_PROVIDER", "claude")
        monkeypatch.setenv("J_AGENT_API_KEY", "test-key")
        (temp_cwd / CONFIG_FILE).write_text(
            'J_AGENT_SYSTEM_PROMPT="Custom override prompt."\n', encoding="utf-8"
        )

        config = Config.from_env()

        assert config.system_prompt.startswith("Custom override prompt.")
