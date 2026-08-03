"""Automatic tool discovery for the ``builtin`` package.

Scans ``src.tools.builtin`` for modules, imports each one, and collects
all concrete ``Tool`` subclasses. This lets new tools be added simply by
dropping a module into ``builtin/`` -- no manual registration needed.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.tools.base import Tool


def discover_builtin_tools() -> list[Tool]:
    """Discover and instantiate all tools in the ``builtin`` package.

    Returns a list of ``Tool`` instances, one per concrete subclass found.
    The ``Tool`` base class itself is excluded.
    """
    from src.tools.base import Tool
    from src.tools.builtin import __path__ as builtin_path

    discovered: list[Tool] = []
    seen_classes: set[type[Tool]] = set()

    for module_info in pkgutil.iter_modules(builtin_path):
        module = importlib.import_module(f"src.tools.builtin.{module_info.name}")

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Tool)
                and attr is not Tool
                and attr not in seen_classes
            ):
                seen_classes.add(attr)
                discovered.append(attr())

    return discovered
