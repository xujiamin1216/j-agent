"""Work context -- binds the agent to a working directory.

The work context provides project-scoped paths for memory, sessions, and
other data. All persistent data is stored under ``<work_dir>/.j-agent/``
so that each working directory has its own isolated state.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class WorkContext:
    """Represents the working directory context for the agent."""

    work_dir: Path

    @classmethod
    def from_cwd(cls) -> WorkContext:
        """Create a WorkContext from the current working directory."""
        return cls(work_dir=Path.cwd().resolve())

    @property
    def data_dir(self) -> Path:
        """Data directory: ``<work_dir>/.j-agent/``.

        Created on first access.
        """
        path = self.work_dir / ".j-agent"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def memory_file(self) -> Path:
        """Path to the project-scoped memory file."""
        return self.data_dir / "memory.json"

    @property
    def sessions_dir(self) -> Path:
        """Path to the project-scoped sessions directory."""
        path = self.data_dir / "sessions"
        path.mkdir(parents=True, exist_ok=True)
        return path
