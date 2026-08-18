"""Structured tracing and cost aggregation (Phase 6).

``Tracer`` collects structured events for LLM calls and tool calls, keeping
running totals of token usage and estimated cost. Events can optionally be
streamed to a JSONL file (``--trace``) for post-hoc analysis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.llm.types import Usage
from src.observability.pricing import estimate_cost


@dataclass
class TraceEvent:
    """A single structured trace record."""

    timestamp: str
    event: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"timestamp": self.timestamp, "event": self.event, **self.data}


class Tracer:
    """Collects trace events and aggregates token usage and cost."""

    def __init__(self, trace_file: Path | None = None) -> None:
        self._events: list[TraceEvent] = []
        self._trace_file = trace_file
        self.llm_calls = 0
        self.tool_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

    def record_llm_call(
        self, model: str, usage: Usage | None, duration_ms: float
    ) -> None:
        """Record one LLM call with its token usage and wall-clock duration."""
        self.llm_calls += 1
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0
        cost = estimate_cost(model, input_tokens, output_tokens)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
        self._record(
            "llm_call",
            {
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "duration_ms": round(duration_ms, 2),
                "cost_usd": round(cost, 6),
            },
        )

    def record_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
        is_error: bool,
        duration_ms: float,
    ) -> None:
        """Record one tool execution with its arguments and outcome."""
        self.tool_calls += 1
        self._record(
            "tool_call",
            {
                "name": name,
                "arguments": arguments,
                "is_error": is_error,
                "duration_ms": round(duration_ms, 2),
            },
        )

    def _record(self, event: str, data: dict[str, Any]) -> None:
        record = TraceEvent(
            timestamp=datetime.now().isoformat(),
            event=event,
            data=data,
        )
        self._events.append(record)
        if self._trace_file is not None:
            with self._trace_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    @property
    def events(self) -> list[TraceEvent]:
        """Return a copy of all recorded events."""
        return list(self._events)

    def summary(self) -> dict[str, Any]:
        """Aggregate totals for a session-end report."""
        return {
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost, 6),
        }
