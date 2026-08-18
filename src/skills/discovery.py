"""Automatic skill discovery.

Scans the ``skills`` directory for subdirectories containing ``SKILL.md``,
parses frontmatter to extract metadata (name, description, script), and
returns ``Skill`` objects. Only metadata is read -- full prompt content
is loaded lazily on invocation (progressive loading).
"""

from __future__ import annotations

from pathlib import Path

from src.skills.skill import Skill, SkillRegistry, _parse_frontmatter

# File name for the skill prompt template inside each skill directory.
SKILL_FILE = "SKILL.md"


def discover_skills(skills_dir: Path | None = None) -> list[Skill]:
    """Discover all skills in the given directory.

    Each subdirectory of *skills_dir* that contains a ``SKILL.md`` file
    is treated as a skill. Only frontmatter is read -- full content is
    loaded on demand.

    Returns a list of ``Skill`` objects. Returns an empty list if
    *skills_dir* is None, does not exist, or contains no valid skills.
    """
    if skills_dir is None:
        return []

    if not skills_dir.is_dir():
        return []

    discovered: list[Skill] = []

    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue

        skill_file = entry / SKILL_FILE
        if not skill_file.is_file():
            continue

        skill = _parse_skill_file(entry, skill_file)
        if skill is not None:
            discovered.append(skill)

    return discovered


def _parse_skill_file(skill_dir: Path, skill_file: Path) -> Skill | None:
    """Parse a SKILL.md file and return a Skill, or None on failure.

    Reads only the frontmatter (progressive loading). The ``name`` field
    defaults to the directory name if not present in frontmatter. The
    ``description`` defaults to the first non-empty line of content if
    not present.
    """
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError:
        return None

    metadata, content = _parse_frontmatter(text)

    name = metadata.get("name", "").strip() or skill_dir.name
    description = metadata.get("description", "").strip()
    script = metadata.get("script", "").strip() or None

    # Fallback: use first non-empty content line as description.
    if not description:
        for line in content.split("\n"):
            line = line.strip()
            if line:
                description = line
                break

    return Skill(
        name=name,
        description=description,
        skill_dir=skill_dir,
        script=script,
    )


def build_skill_descriptions(work_dir: Path | None = None) -> str:
    """Build skill description text for system prompt injection.

    Discovers skills from ``<work_dir>/.j-agent/skills/`` and returns
    a formatted description list. Returns an empty string if no skills
    are found or *work_dir* is None.
    """
    if work_dir is None:
        return ""

    skills_dir = work_dir / ".j-agent" / "skills"
    skills = discover_skills(skills_dir)
    if not skills:
        return ""

    registry = SkillRegistry()
    for skill in skills:
        registry.register(skill)

    return registry.to_descriptions()
