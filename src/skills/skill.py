"""Skill -- user-defined prompt templates with natural language triggering.

Skills are markdown files (SKILL.md) stored in ``<work_dir>/.j-agent/skills/
<name>/``. Each skill has a YAML frontmatter with ``name``, ``description``
(including trigger conditions), and an optional ``script`` field.

The LLM sees skill descriptions in the system prompt and invokes skills via
the ``use_skill`` tool when the user's request matches a skill's trigger
conditions. Skill content is loaded lazily (progressive loading): only
metadata is scanned at startup, full prompt content is read from disk on
invocation.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Maximum seconds for script execution.
SCRIPT_TIMEOUT = 30

# Regex for @file:path references in skill content.
_FILE_REF_PATTERN = re.compile(r"@file:\s*(\S+)")

# Regex for frontmatter parsing.
_FRONTMATTER_DELIMITER = "---"


@dataclass
class Skill:
    """A skill prompt template with lazy-loaded content.

    Only metadata (name, description, script) is held in memory. The full
    prompt content is read from ``SKILL.md`` on demand via ``load_content()``
    or ``expand()``.
    """

    name: str
    description: str
    skill_dir: Path
    script: str | None = None

    @property
    def skill_file(self) -> Path:
        """Path to the SKILL.md file."""
        return self.skill_dir / "SKILL.md"

    def load_content(self) -> str:
        """Read the full prompt content from SKILL.md (after frontmatter).

        Raises FileNotFoundError if SKILL.md does not exist.
        """
        text = self.skill_file.read_text(encoding="utf-8")
        _, content = _parse_frontmatter(text)
        return content.strip()

    def expand(self, args: str = "") -> str:
        """Load content and expand all template variables and references.

        Expansion order:
        1. Execute script (if any), capture stdout
        2. Replace ``@file:path`` references with file contents
        3. Replace ``{{script_output}}`` with script stdout
        4. Replace ``{{args}}`` with user arguments

        Returns the fully expanded prompt string.
        """
        content = self.load_content()

        # 1. Execute script if specified.
        script_output = self._run_script() if self.script else ""

        # 2. Replace @file:path references.
        content = self._expand_file_refs(content)

        # 3. Replace {{script_output}}.
        if "{{script_output}}" in content:
            content = content.replace("{{script_output}}", script_output)
        elif script_output:
            content = f"{content}\n\n{script_output}"

        # 4. Replace {{args}}.
        if "{{args}}" in content:
            content = content.replace("{{args}}", args)
        elif args:
            content = f"{content}\n\n{args}"

        return content

    def _run_script(self) -> str:
        """Execute the skill's script and return stdout.

        On error or timeout, returns an error message string.
        """
        script_path = self.skill_dir / self.script  # type: ignore[arg-type]
        if not script_path.exists():
            return f"[脚本不存在: {self.script}]"

        try:
            proc = subprocess.run(
                str(script_path),
                shell=True,
                capture_output=True,
                text=True,
                timeout=SCRIPT_TIMEOUT,
                cwd=str(self.skill_dir),
            )
        except subprocess.TimeoutExpired:
            return f"[脚本超时: {SCRIPT_TIMEOUT}秒]"

        if proc.returncode != 0 and proc.stderr:
            return f"[脚本错误: {proc.stderr.strip()}]"

        return proc.stdout.strip()

    def _expand_file_refs(self, content: str) -> str:
        """Replace ``@file:path`` directives with file contents.

        Path resolution: first relative to the skill directory, then
        relative to the working directory (``skill_dir.parent.parent.parent``
        which is ``<work_dir>/.j-agent/skills/../..`` = ``<work_dir>``).

        Missing files are replaced with an error placeholder.
        """

        def _replace(match: re.Match[str]) -> str:
            path_str = match.group(1)
            # Try skill directory first.
            candidate = self.skill_dir / path_str
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8").strip()
            # Fall back to working directory.
            work_dir = self.skill_dir.parent.parent.parent
            candidate = work_dir / path_str
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8").strip()
            return f"[引用文件不存在: {path_str}]"

        return _FILE_REF_PATTERN.sub(_replace, content)


class SkillRegistry:
    """Manages skill registration, lookup, and invocation."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills: dict[str, Skill] = {}
        self._skills_dir = skills_dir

    def register(self, skill: Skill) -> None:
        """Register a skill. Raises ValueError if name is already taken."""
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' is already registered")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        """Look up a skill by name."""
        return self._skills.get(name)

    def list(self) -> list[Skill]:
        """List all registered skills (metadata only)."""
        return list(self._skills.values())

    def names(self) -> list[str]:
        """List all registered skill names."""
        return list(self._skills.keys())

    def invoke(self, name: str, args: str = "") -> str | None:
        """Invoke a skill by name, returning the expanded prompt.

        Returns None if the skill is not found.
        """
        skill = self._skills.get(name)
        if skill is None:
            return None
        return skill.expand(args)

    def to_descriptions(self) -> str:
        """Generate a text list of skill descriptions for system prompt injection."""
        if not self._skills:
            return ""
        lines = []
        for skill in self._skills.values():
            lines.append(f"- **{skill.name}**: {skill.description}")
        return "\n".join(lines)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from markdown text.

    Returns a tuple of (metadata_dict, content_after_frontmatter).
    Supports simple ``key: value`` pairs and folded scalars (``>``).

    Does not depend on pyyaml -- only the minimal subset needed for
    skill files is handled.
    """
    lines = text.split("\n")

    # Must start with ---.
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        return {}, text

    # Find closing ---.
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIMITER:
            end_idx = i
            break

    if end_idx is None:
        return {}, text

    frontmatter_lines = lines[1:end_idx]
    content_lines = lines[end_idx + 1:]

    metadata: dict[str, str] = {}
    current_key: str | None = None
    current_value: list[str] = []

    def _flush() -> None:
        """Save the current key-value pair to metadata."""
        nonlocal current_key, current_value
        if current_key is not None:
            metadata[current_key] = " ".join(current_value).strip()
        current_key = None
        current_value = []

    for line in frontmatter_lines:
        # Check if this is a continuation line (indented).
        if line.startswith("  ") or line.startswith("\t"):
            if current_key is not None:
                current_value.append(line.strip())
            continue

        # New key-value pair.
        _flush()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value in (">", "|"):
                # Multi-line indicator -- collect following indented lines.
                current_key = key
                current_value = []
            elif value:
                metadata[key] = value
            else:
                # Empty value, might be multi-line without indicator.
                current_key = key
                current_value = []

    _flush()

    content = "\n".join(content_lines).strip()
    return metadata, content
