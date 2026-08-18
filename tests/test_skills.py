"""Tests for the skills module."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from src.skills.discovery import build_skill_descriptions, discover_skills
from src.skills.skill import Skill, SkillRegistry, _parse_frontmatter
from src.tools.base import Tool, ToolRegistry
from src.tools.builtin.skill import UseSkillTool
from src.tools.discovery import discover_builtin_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_skill_dir(
    base: Path,
    name: str,
    content: str = "",
    script: str | None = None,
    script_content: str | None = None,
    extra_files: dict[str, str] | None = None,
) -> Path:
    """Create a skill directory with SKILL.md and optional files.

    Returns the skill directory path.
    """
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    if script and script_content is not None:
        script_path = skill_dir / script
        script_path.write_text(script_content, encoding="utf-8")
        script_path.chmod(0o755)
    if extra_files:
        for fname, fcontent in extra_files.items():
            (skill_dir / fname).write_text(fcontent, encoding="utf-8")
    return skill_dir


def make_work_dir(tmp_path: Path) -> Path:
    """Create a work directory with skills dir structure."""
    work_dir = tmp_path / "project"
    skills_dir = work_dir / ".j-agent" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_no_frontmatter(self):
        text = "Hello world\nSecond line"
        metadata, content = _parse_frontmatter(text)
        assert metadata == {}
        assert content == "Hello world\nSecond line"

    def test_simple_key_value(self):
        text = dedent("""\
            ---
            name: commit
            description: A commit skill
            ---
            Content here""")
        metadata, content = _parse_frontmatter(text)
        assert metadata["name"] == "commit"
        assert metadata["description"] == "A commit skill"
        assert content == "Content here"

    def test_folded_scalar_description(self):
        text = dedent("""\
            ---
            name: commit
            description: >
              Help create a commit.
              TRIGGER when: user wants to commit.
              DO NOT TRIGGER when: general git question.
            script: git-status.sh
            ---
            Content here""")
        metadata, content = _parse_frontmatter(text)
        assert metadata["name"] == "commit"
        assert "Help create a commit" in metadata["description"]
        assert "TRIGGER when" in metadata["description"]
        assert "DO NOT TRIGGER when" in metadata["description"]
        assert metadata["script"] == "git-status.sh"
        assert content == "Content here"

    def test_empty_frontmatter_value(self):
        text = dedent("""\
            ---
            name: test
            ---
            Content""")
        metadata, content = _parse_frontmatter(text)
        assert metadata["name"] == "test"
        assert content == "Content"

    def test_missing_closing_delimiter(self):
        text = "---\nname: test\nContent without closing"
        metadata, content = _parse_frontmatter(text)
        assert metadata == {}
        assert "Content without closing" in content


# ---------------------------------------------------------------------------
# Skill.load_content
# ---------------------------------------------------------------------------


class TestSkillLoadContent:
    def test_load_content_with_frontmatter(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path,
            "test",
            content="---\nname: test\ndescription: Test\n---\nActual content",
        )
        skill = Skill(name="test", description="Test", skill_dir=skill_dir)
        assert skill.load_content() == "Actual content"

    def test_load_content_no_frontmatter(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path, "test", content="Just content"
        )
        skill = Skill(name="test", description="Test", skill_dir=skill_dir)
        assert skill.load_content() == "Just content"

    def test_load_content_file_not_found(self, tmp_path: Path):
        skill = Skill(
            name="test", description="Test", skill_dir=tmp_path / "nonexistent"
        )
        with pytest.raises(FileNotFoundError):
            skill.load_content()


# ---------------------------------------------------------------------------
# Skill.expand -- {{args}}
# ---------------------------------------------------------------------------


class TestSkillExpandArgs:
    def test_replace_args_placeholder(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path, "echo", content="Echo: {{args}}"
        )
        skill = Skill(name="echo", description="Echo", skill_dir=skill_dir)
        assert skill.expand("hello") == "Echo: hello"

    def test_append_args_no_placeholder(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path, "echo", content="Fixed prompt"
        )
        skill = Skill(name="echo", description="Echo", skill_dir=skill_dir)
        assert skill.expand("extra") == "Fixed prompt\n\nextra"

    def test_no_args_no_placeholder(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path, "echo", content="Fixed prompt"
        )
        skill = Skill(name="echo", description="Echo", skill_dir=skill_dir)
        assert skill.expand() == "Fixed prompt"

    def test_empty_args_with_placeholder(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path, "echo", content="Echo: {{args}}"
        )
        skill = Skill(name="echo", description="Echo", skill_dir=skill_dir)
        assert skill.expand("") == "Echo: "


# ---------------------------------------------------------------------------
# Skill.expand -- script
# ---------------------------------------------------------------------------


class TestSkillExpandScript:
    def test_script_output_replaced(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path,
            "commit",
            content="Result:\n{{script_output}}",
            script="status.sh",
            script_content='#!/bin/bash\necho "branch: main"',
        )
        skill = Skill(
            name="commit",
            description="Commit",
            skill_dir=skill_dir,
            script="status.sh",
        )
        result = skill.expand()
        assert "branch: main" in result
        assert "{{script_output}}" not in result

    def test_script_output_appended(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path,
            "commit",
            content="Fixed prompt",
            script="status.sh",
            script_content='#!/bin/bash\necho "status: ok"',
        )
        skill = Skill(
            name="commit",
            description="Commit",
            skill_dir=skill_dir,
            script="status.sh",
        )
        result = skill.expand()
        assert "Fixed prompt" in result
        assert "status: ok" in result

    def test_script_not_found(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path,
            "commit",
            content="Result:\n{{script_output}}",
        )
        skill = Skill(
            name="commit",
            description="Commit",
            skill_dir=skill_dir,
            script="missing.sh",
        )
        result = skill.expand()
        assert "[脚本不存在: missing.sh]" in result

    def test_script_failure(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path,
            "commit",
            content="Result:\n{{script_output}}",
            script="fail.sh",
            script_content='#!/bin/bash\necho "error msg" >&2\nexit 1',
        )
        skill = Skill(
            name="commit",
            description="Commit",
            skill_dir=skill_dir,
            script="fail.sh",
        )
        result = skill.expand()
        assert "[脚本错误:" in result
        assert "error msg" in result


# ---------------------------------------------------------------------------
# Skill.expand -- @file: references
# ---------------------------------------------------------------------------


class TestSkillExpandFileRef:
    def test_file_ref_skill_local(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path,
            "review",
            content="Conventions:\n@file: conventions.md",
            extra_files={"conventions.md": "Be concise."},
        )
        skill = Skill(name="review", description="Review", skill_dir=skill_dir)
        result = skill.expand()
        assert "Be concise." in result
        assert "@file:" not in result

    def test_file_ref_work_dir_fallback(self, tmp_path: Path):
        work_dir = make_work_dir(tmp_path)
        skill_dir = make_skill_dir(
            work_dir / ".j-agent" / "skills",
            "review",
            content="Project:\n@file: AGENT.md",
        )
        (work_dir / "AGENT.md").write_text("Project rules.", encoding="utf-8")
        skill = Skill(name="review", description="Review", skill_dir=skill_dir)
        result = skill.expand()
        assert "Project rules." in result

    def test_file_ref_missing(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path,
            "review",
            content="Conventions:\n@file: missing.md",
        )
        skill = Skill(name="review", description="Review", skill_dir=skill_dir)
        result = skill.expand()
        assert "[引用文件不存在: missing.md]" in result

    def test_multiple_file_refs(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path,
            "review",
            content="@file: a.md\n---\n@file: b.md",
            extra_files={"a.md": "Content A", "b.md": "Content B"},
        )
        skill = Skill(name="review", description="Review", skill_dir=skill_dir)
        result = skill.expand()
        assert "Content A" in result
        assert "Content B" in result


# ---------------------------------------------------------------------------
# Skill.expand -- combined
# ---------------------------------------------------------------------------


class TestSkillExpandCombined:
    def test_script_args_and_file_ref(self, tmp_path: Path):
        skill_dir = make_skill_dir(
            tmp_path,
            "commit",
            content=dedent("""\
                Help commit.

                ## Status
                {{script_output}}

                ## Conventions
                @file: rules.md

                ## Context
                {{args}}"""),
            script="status.sh",
            script_content='#!/bin/bash\necho "clean"',
            extra_files={"rules.md": "Use conventional commits."},
        )
        skill = Skill(
            name="commit",
            description="Commit",
            skill_dir=skill_dir,
            script="status.sh",
        )
        result = skill.expand("fix bug")
        assert "clean" in result
        assert "Use conventional commits." in result
        assert "fix bug" in result
        assert "{{" not in result
        assert "@file:" not in result


# ---------------------------------------------------------------------------
# Progressive loading
# ---------------------------------------------------------------------------


class TestProgressiveLoading:
    def test_content_not_read_at_creation(self, tmp_path: Path):
        """Skill creation should not read SKILL.md content."""
        skill_dir = make_skill_dir(
            tmp_path, "test", content="---\nname: test\n---\nSecret content"
        )
        skill = Skill(name="test", description="Test", skill_dir=skill_dir)
        # Skill object holds only metadata; content is not loaded yet.
        assert skill.name == "test"
        assert skill.description == "Test"
        # Content is loaded on demand.
        assert "Secret content" in skill.load_content()


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------


class TestSkillRegistry:
    def _make_skill(self, tmp_path: Path, name: str = "test") -> Skill:
        skill_dir = make_skill_dir(
            tmp_path, name, content=f"Skill {name} content"
        )
        return Skill(name=name, description=f"Skill {name}", skill_dir=skill_dir)

    def test_register_and_get(self, tmp_path: Path):
        registry = SkillRegistry()
        skill = self._make_skill(tmp_path, "commit")
        registry.register(skill)
        assert registry.get("commit") is skill

    def test_get_nonexistent(self):
        registry = SkillRegistry()
        assert registry.get("nonexistent") is None

    def test_register_duplicate_raises(self, tmp_path: Path):
        registry = SkillRegistry()
        skill = self._make_skill(tmp_path, "commit")
        registry.register(skill)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(skill)

    def test_list(self, tmp_path: Path):
        registry = SkillRegistry()
        registry.register(self._make_skill(tmp_path, "a"))
        registry.register(self._make_skill(tmp_path, "b"))
        assert len(registry.list()) == 2

    def test_names(self, tmp_path: Path):
        registry = SkillRegistry()
        registry.register(self._make_skill(tmp_path, "a"))
        registry.register(self._make_skill(tmp_path, "b"))
        assert set(registry.names()) == {"a", "b"}

    def test_invoke_existing(self, tmp_path: Path):
        registry = SkillRegistry()
        skill_dir = make_skill_dir(
            tmp_path, "echo", content="Echo: {{args}}"
        )
        registry.register(
            Skill(name="echo", description="Echo", skill_dir=skill_dir)
        )
        result = registry.invoke("echo", "hello")
        assert result == "Echo: hello"

    def test_invoke_nonexistent(self):
        registry = SkillRegistry()
        assert registry.invoke("nonexistent") is None

    def test_to_descriptions(self, tmp_path: Path):
        registry = SkillRegistry()
        registry.register(self._make_skill(tmp_path, "a"))
        registry.register(self._make_skill(tmp_path, "b"))
        desc = registry.to_descriptions()
        assert "**a**" in desc
        assert "**b**" in desc

    def test_to_descriptions_empty(self):
        registry = SkillRegistry()
        assert registry.to_descriptions() == ""


# ---------------------------------------------------------------------------
# discover_skills
# ---------------------------------------------------------------------------


class TestDiscoverSkills:
    def test_discover_valid_skills(self, tmp_path: Path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        make_skill_dir(
            skills_dir,
            "commit",
            content=dedent("""\
                ---
                name: commit
                description: Create a commit. TRIGGER when: user wants to commit.
                ---
                Help commit."""),
        )
        make_skill_dir(
            skills_dir,
            "review",
            content=dedent("""\
                ---
                name: review
                description: Review code. TRIGGER when: user asks for review.
                ---
                Help review."""),
        )
        skills = discover_skills(skills_dir)
        assert len(skills) == 2
        names = {s.name for s in skills}
        assert names == {"commit", "review"}

    def test_discover_with_script(self, tmp_path: Path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        make_skill_dir(
            skills_dir,
            "commit",
            content=dedent("""\
                ---
                name: commit
                description: Create a commit.
                script: status.sh
                ---
                Help commit."""),
            script="status.sh",
            script_content='#!/bin/bash\necho ok',
        )
        skills = discover_skills(skills_dir)
        assert len(skills) == 1
        assert skills[0].script == "status.sh"

    def test_discover_no_frontmatter(self, tmp_path: Path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        make_skill_dir(
            skills_dir, "simple", content="Just a simple skill prompt."
        )
        skills = discover_skills(skills_dir)
        assert len(skills) == 1
        assert skills[0].name == "simple"
        # Description defaults to first content line.
        assert skills[0].description == "Just a simple skill prompt."

    def test_discover_name_from_directory(self, tmp_path: Path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        make_skill_dir(
            skills_dir,
            "my-skill",
            content="---\ndescription: Test\n---\nContent",
        )
        skills = discover_skills(skills_dir)
        assert len(skills) == 1
        assert skills[0].name == "my-skill"

    def test_discover_skip_dir_without_skill_file(self, tmp_path: Path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        make_skill_dir(skills_dir, "valid", content="Content")
        (skills_dir / "invalid").mkdir()
        skills = discover_skills(skills_dir)
        assert len(skills) == 1
        assert skills[0].name == "valid"

    def test_discover_empty_dir(self, tmp_path: Path):
        skills_dir = tmp_path / "empty"
        skills_dir.mkdir()
        assert discover_skills(skills_dir) == []

    def test_discover_nonexistent_dir(self, tmp_path: Path):
        assert discover_skills(tmp_path / "nonexistent") == []

    def test_discover_none_dir(self):
        assert discover_skills(None) == []


# ---------------------------------------------------------------------------
# build_skill_descriptions
# ---------------------------------------------------------------------------


class TestBuildSkillDescriptions:
    def test_with_skills(self, tmp_path: Path):
        work_dir = make_work_dir(tmp_path)
        skills_dir = work_dir / ".j-agent" / "skills"
        make_skill_dir(
            skills_dir,
            "commit",
            content=dedent("""\
                ---
                name: commit
                description: Create a commit. TRIGGER when: user wants to commit.
                ---
                Help commit."""),
        )
        desc = build_skill_descriptions(work_dir)
        assert "commit" in desc
        assert "TRIGGER when" in desc

    def test_without_skills(self, tmp_path: Path):
        work_dir = make_work_dir(tmp_path)
        assert build_skill_descriptions(work_dir) == ""

    def test_none_work_dir(self):
        assert build_skill_descriptions(None) == ""


# ---------------------------------------------------------------------------
# UseSkillTool
# ---------------------------------------------------------------------------


class TestUseSkillTool:
    def test_execute_success(self, tmp_path: Path):
        work_dir = make_work_dir(tmp_path)
        skills_dir = work_dir / ".j-agent" / "skills"
        make_skill_dir(
            skills_dir,
            "echo",
            content="Echo: {{args}}",
        )
        tool = UseSkillTool()
        tool.work_dir = work_dir
        result = tool.execute(skill_name="echo", args="hello")
        assert "Echo: hello" in result

    def test_execute_skill_not_found(self, tmp_path: Path):
        work_dir = make_work_dir(tmp_path)
        tool = UseSkillTool()
        tool.work_dir = work_dir
        result = tool.execute(skill_name="nonexistent")
        assert "not found" in result

    def test_execute_no_skills(self, tmp_path: Path):
        work_dir = make_work_dir(tmp_path)
        tool = UseSkillTool()
        tool.work_dir = work_dir
        result = tool.execute(skill_name="anything")
        assert "not found" in result
        assert "(none)" in result

    def test_auto_discovery_includes_use_skill(self):
        tools = discover_builtin_tools()
        names = {t.name for t in tools}
        assert "use_skill" in names

    def test_is_tool_instance(self):
        tool = UseSkillTool()
        assert isinstance(tool, Tool)

    def test_tool_spec_valid(self):
        tool = UseSkillTool()
        spec = tool.to_spec()
        assert spec.name == "use_skill"
        assert spec.description
        assert "skill_name" in spec.parameters["properties"]
        assert "args" in spec.parameters["properties"]
        assert spec.parameters["required"] == ["skill_name"]

    def test_registry_sets_work_dir(self, tmp_path: Path):
        work_dir = make_work_dir(tmp_path)
        registry = ToolRegistry(work_dir=work_dir)
        tool = UseSkillTool()
        registry.register(tool)
        assert tool.work_dir == work_dir
