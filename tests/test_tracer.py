"""Tests for observability (Phase 6).

Covers model pricing lookup/cost estimation and the Tracer's event
collection, aggregation, and JSONL file output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.llm.types import Usage
from src.observability.pricing import estimate_cost, get_pricing
from src.observability.tracer import Tracer, TraceEvent


class TestPricing:
    def test_get_pricing_claude(self):
        assert get_pricing("claude-sonnet-4-20250514") == (3.0, 15.0)

    def test_get_pricing_prefers_longest_keyword(self):
        # "gpt-4o-mini" must match the mini entry, not "gpt-4o".
        assert get_pricing("gpt-4o-mini") == (0.15, 0.6)

    def test_get_pricing_case_insensitive(self):
        assert get_pricing("Claude-Opus-4") == (15.0, 75.0)

    def test_get_pricing_unknown(self):
        assert get_pricing("some-custom-model") is None

    def test_estimate_cost(self):
        # 1M input + 1M output for claude-sonnet = 3 + 15 = 18 USD.
        cost = estimate_cost("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
        assert cost == 18.0

    def test_estimate_cost_partial_tokens(self):
        cost = estimate_cost("gpt-4o-mini", 500_000, 500_000)
        assert cost == 0.375

    def test_estimate_cost_unknown_zero(self):
        assert estimate_cost("unknown-model", 100, 100) == 0.0


class TestTracer:
    def test_record_llm_call_aggregates(self):
        tracer = Tracer()
        tracer.record_llm_call(
            "claude-sonnet-4-20250514", Usage(1000, 500), 123.45
        )
        assert tracer.llm_calls == 1
        assert tracer.total_input_tokens == 1000
        assert tracer.total_output_tokens == 500
        assert tracer.total_cost == pytest.approx(
            estimate_cost("claude-sonnet-4-20250514", 1000, 500)
        )

    def test_record_llm_call_none_usage(self):
        tracer = Tracer()
        tracer.record_llm_call("unknown", None, 1.0)
        assert tracer.total_input_tokens == 0
        assert tracer.total_output_tokens == 0
        assert tracer.total_cost == 0.0

    def test_record_tool_call(self):
        tracer = Tracer()
        tracer.record_tool_call("bash", {"command": "ls"}, False, 5.0)
        assert tracer.tool_calls == 1
        assert tracer.events[0].event == "tool_call"
        assert tracer.events[0].data["name"] == "bash"

    def test_summary(self):
        tracer = Tracer()
        tracer.record_llm_call("claude-sonnet-4-20250514", Usage(1000, 500), 1.0)
        tracer.record_tool_call("grep", {"pattern": "x"}, False, 2.0)
        s = tracer.summary()
        assert s["llm_calls"] == 1
        assert s["tool_calls"] == 1
        assert s["input_tokens"] == 1000
        assert s["output_tokens"] == 500
        assert s["total_cost_usd"] == pytest.approx(
            estimate_cost("claude-sonnet-4-20250514", 1000, 500)
        )

    def test_events_returns_copy(self):
        tracer = Tracer()
        tracer.record_llm_call("m", None, 1.0)
        events = tracer.events
        events.clear()
        assert len(tracer.events) == 1

    def test_trace_file_written(self, tmp_path: Path):
        trace_file = tmp_path / "trace.jsonl"
        tracer = Tracer(trace_file=trace_file)
        tracer.record_llm_call("m", Usage(10, 20), 1.0)
        tracer.record_tool_call("grep", {"pattern": "x"}, False, 2.0)

        lines = trace_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["event"] == "llm_call"
        assert first["input_tokens"] == 10
        assert first["output_tokens"] == 20


class TestTraceEvent:
    def test_to_dict(self):
        e = TraceEvent(timestamp="t", event="llm_call", data={"model": "m"})
        assert e.to_dict() == {"timestamp": "t", "event": "llm_call", "model": "m"}
