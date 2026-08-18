"""Tool risk classification and dangerous-command detection.

Phase 4 (permission system). Risk levels are plain strings so they compare
and serialize cleanly. The dangerous-command detector uses regex pattern
matching against shell command strings (no shell parsing is attempted).
"""

from __future__ import annotations

import re


class RiskLevel:
    """Risk levels for tool operations.

    - ``safe``: read-only or scoped operations that need no confirmation.
    - ``confirm``: state-mutating or code-executing operations that should
      be confirmed by the user.
    - ``dangerous``: potentially destructive or irreversible operations.
    """

    SAFE = "safe"
    CONFIRM = "confirm"
    DANGEROUS = "dangerous"

    ALL = (SAFE, CONFIRM, DANGEROUS)


# Regex patterns that flag a shell command as dangerous. Matching is
# case-sensitive and uses word boundaries where possible to avoid false
# positives (e.g. "rm" inside "format" or "git" inside "legitimate").
DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    # File / directory removal.
    re.compile(r"\brm\b"),
    re.compile(r"\brmdir\b"),
    # Destructive / history-rewriting git operations.
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bgit\s+reset\b"),
    re.compile(r"\bgit\s+clean\b"),
    re.compile(r"\bgit\s+branch\s+-D\b"),
    re.compile(r"\bgit\s+checkout\s+--"),
    # Privilege escalation.
    re.compile(r"\bsudo\b"),
    # Recursive permission / ownership changes.
    re.compile(r"\bchmod\s+-R\b"),
    re.compile(r"\bchown\s+-R\b"),
    # Disk / system level operations.
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+if="),
    re.compile(r"\btruncate\b"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\bhalt\b"),
    # Fork bomb.
    re.compile(r":\(\)\s*\{"),
    # Pipe into a shell / sudo (curl | sh style).
    re.compile(r"\|\s*(ba)?sh\b"),
    re.compile(r"\|\s*sudo\b"),
]


def detect_dangerous_command(command: str) -> bool:
    """Return True if *command* matches any dangerous pattern.

    The command string is scanned as a whole; no shell tokenization is done.
    """
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(command):
            return True
    return False


def classify_command_risk(command: str) -> str:
    """Classify a shell command as ``RiskLevel.CONFIRM`` or ``DANGEROUS``.

    Used to escalate the static risk of a command-executing tool (e.g.
    ``bash``) based on the actual command text.
    """
    if detect_dangerous_command(command):
        return RiskLevel.DANGEROUS
    return RiskLevel.CONFIRM
