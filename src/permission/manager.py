"""Permission manager -- gate tool execution by risk and user mode.

Phase 4 (permission system). Decides whether a tool call may proceed based on:

1. The tool's static risk level (``safe`` / ``confirm`` / ``dangerous``).
2. Dynamic escalation from dangerous-command detection (a ``confirm`` tool
   carrying a ``command`` argument is escalated to ``dangerous`` if the
   command matches dangerous patterns).
3. The current permission mode (``auto`` / ``ask`` / ``yolo``).

Interactive confirmation is delegated to an injected ``ask_callback`` so the
manager stays UI-agnostic: the CLI supplies a rich-based prompt, while tests
inject a deterministic stub. Without a callback, non-safe operations are
denied by default (fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.permission.risk import RiskLevel, classify_command_risk


class PermissionMode:
    """Permission modes controlling when the user is prompted."""

    AUTO = "auto"  # allow safe; prompt for confirm/dangerous
    ASK = "ask"    # prompt for everything
    YOLO = "yolo"  # never prompt

    ALL = (AUTO, ASK, YOLO)


# Callback type: (tool_name, arguments, risk_level) -> bool (allow?).
AskCallback = Callable[[str, dict[str, Any], str], bool]


@dataclass
class PermissionDecision:
    """Outcome of a permission check."""

    allowed: bool
    risk_level: str
    reason: str


class PermissionManager:
    """Gates tool execution according to risk level and permission mode."""

    def __init__(
        self,
        mode: str = PermissionMode.AUTO,
        risk_map: dict[str, str] | None = None,
        ask_callback: AskCallback | None = None,
    ) -> None:
        self.mode = mode
        self._risk_map = risk_map or {}
        self._ask_callback = ask_callback

    def check(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        """Decide whether a tool call is allowed.

        Returns a ``PermissionDecision``; the caller is responsible for
        honoring ``allowed=False`` (e.g. by not executing the tool).
        """
        risk = self._effective_risk(tool_name, arguments)

        if self.mode == PermissionMode.YOLO:
            return PermissionDecision(
                allowed=True, risk_level=risk, reason="yolo 模式：自动放行"
            )

        if self.mode == PermissionMode.ASK:
            return self._prompt(tool_name, arguments, risk)

        # AUTO mode: safe tools run without prompting.
        if risk == RiskLevel.SAFE:
            return PermissionDecision(
                allowed=True, risk_level=risk, reason="safe 工具：自动放行"
            )

        return self._prompt(tool_name, arguments, risk)

    def _effective_risk(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Determine the effective risk for a tool call.

        Starts from the tool's static risk level and escalates a ``confirm``
        tool carrying a ``command`` argument to ``dangerous`` if the command
        matches dangerous patterns.
        """
        base = self._risk_map.get(tool_name, RiskLevel.SAFE)
        command = arguments.get("command")
        if base == RiskLevel.CONFIRM and isinstance(command, str) and command:
            return classify_command_risk(command)
        return base

    def _prompt(
        self, tool_name: str, arguments: dict[str, Any], risk: str
    ) -> PermissionDecision:
        """Ask the user (via callback) whether to allow the operation."""
        if self._ask_callback is None:
            return PermissionDecision(
                allowed=False,
                risk_level=risk,
                reason="需要人工确认（无可用确认回调）",
            )
        if self._ask_callback(tool_name, arguments, risk):
            return PermissionDecision(
                allowed=True, risk_level=risk, reason="用户已确认"
            )
        return PermissionDecision(
            allowed=False, risk_level=risk, reason="用户拒绝"
        )
