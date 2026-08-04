"""Tests for context manager -- cut, compression, and config validation."""

import pytest

from src.llm.base import LLMProvider
from src.llm.types import Message, ToolCall
from src.memory.context_manager import (
    ContextManager,
    ContextManagerConfig,
    SUMMARY_PREFIX,
)
from src.memory.token_counter import HeuristicCounter


class MockProvider(LLMProvider):
    """Mock LLM provider for testing compression."""

    def __init__(self, response: str = "这是摘要") -> None:
        self._response = response
        self.last_messages: list[Message] | None = None

    def chat(self, messages, tools=None, system=None):
        self.last_messages = messages
        return Message.assistant(self._response)


class TestSafeCut:
    def _make_ctx(self):
        return ContextManager(HeuristicCounter(), MockProvider())

    def test_cut_at_user_boundary_safe(self):
        ctx = self._make_ctx()
        messages = [Message.user("a"), Message.assistant("b"), Message.user("c")]
        assert ctx._is_safe_cut(messages, 2) is True

    def test_cut_at_assistant_unsafe(self):
        """Cutting so the first retained message is assistant is unsafe."""
        ctx = self._make_ctx()
        messages = [Message.user("a"), Message.assistant("b"), Message.user("c")]
        assert ctx._is_safe_cut(messages, 1) is False

    def test_cut_at_tool_result_unsafe(self):
        ctx = self._make_ctx()
        messages = [
            Message.user("do it"),
            Message.assistant("calling", tool_calls=[ToolCall(id="tc1", name="echo", arguments={})]),
            Message.tool("tc1", "result"),
        ]
        # Cut at 2: curr is tool -> unsafe
        assert ctx._is_safe_cut(messages, 2) is False

    def test_cut_between_tool_results_unsafe(self):
        """Cutting between two consecutive tool results (multi-tool call) is unsafe."""
        ctx = self._make_ctx()
        messages = [
            Message.user("do it"),
            Message.assistant("calling", tool_calls=[
                ToolCall(id="tc1", name="echo", arguments={}),
                ToolCall(id="tc2", name="echo", arguments={}),
            ]),
            Message.tool("tc1", "result1"),
            Message.tool("tc2", "result2"),
        ]
        # Cut at 3: curr is tool -> unsafe
        assert ctx._is_safe_cut(messages, 3) is False

    def test_cut_after_tool_result_at_user_safe(self):
        ctx = self._make_ctx()
        messages = [
            Message.user("do it"),
            Message.assistant("calling", tool_calls=[ToolCall(id="tc1", name="echo", arguments={})]),
            Message.tool("tc1", "result"),
            Message.user("next"),
        ]
        # Cut at 3: curr is user -> safe
        assert ctx._is_safe_cut(messages, 3) is True

    def test_cut_at_boundaries(self):
        ctx = self._make_ctx()
        messages = [Message.user("a")]
        assert ctx._is_safe_cut(messages, 0) is True
        assert ctx._is_safe_cut(messages, 1) is True


class TestFindCut:
    def _make_ctx(self, config=None):
        return ContextManager(HeuristicCounter(), MockProvider(), config)

    def test_finds_cut_at_60_percent(self):
        """With a large threshold, cut is at the 60% position."""
        ctx = self._make_ctx(ContextManagerConfig(max_context_tokens=10000))
        messages = [Message.user(f"msg {i}") for i in range(10)]
        # start = int(10 * 0.6) = 6, recent at 6 = 4 msgs * ~5 tokens = 20 < limit
        cut = ctx._find_cut(messages, threshold=8000)
        assert cut == 6

    def test_recent_exceeds_limit_moves_forward(self):
        """When recent at 60% exceeds limit, cut moves forward."""
        ctx = self._make_ctx(ContextManagerConfig(max_context_tokens=100))
        messages = [Message.user(f"msg {i}") for i in range(10)]
        # Each msg ~5 tokens. threshold=80, limit=int(80*0.4*1.2)=38
        # At 6: recent = 4*5=20 < 38 -> cut at 6
        # Wait, 20 < 38, so cut at 6. Let me use a smaller threshold.
        # threshold=30, limit=int(30*0.4*1.2)=14
        # At 6: 4*5=20 > 14. At 7: 3*5=15 > 14. At 8: 2*5=10 <= 14. Cut = 8.
        cut = ctx._find_cut(messages, threshold=30)
        assert cut == 8

    def test_finds_safe_cut_around_tool_pairs(self):
        """Cut skips tool results to find a user boundary."""
        ctx = self._make_ctx(ContextManagerConfig(max_context_tokens=10000))
        messages = [
            Message.user(f"u{i}") for i in range(6)
        ] + [
            Message.assistant("call", tool_calls=[ToolCall(id="tc1", name="t", arguments={})]),
            Message.tool("tc1", "result"),
            Message.user("after1"),
            Message.user("after2"),
        ]
        # 10 messages, start = 6
        # i=6: assistant -> unsafe. i=7: tool -> unsafe. i=8: user -> safe.
        cut = ctx._find_cut(messages, threshold=8000)
        assert cut == 8

    def test_too_few_messages_returns_0(self):
        ctx = self._make_ctx()
        messages = [Message.user("only one")]
        cut = ctx._find_cut(messages, threshold=1000)
        assert cut == 0

    def test_no_safe_cut_returns_0(self):
        """When no user message exists after compress_ratio, return 0."""
        ctx = self._make_ctx(ContextManagerConfig(max_context_tokens=10000))
        messages = [
            Message.user(f"u{i}") for i in range(6)
        ] + [
            Message.assistant("call", tool_calls=[ToolCall(id="tc1", name="t", arguments={})]),
            Message.tool("tc1", "r1"),
            Message.tool("tc1", "r2"),
            Message.tool("tc1", "r3"),
        ]
        # 10 messages, start = 6
        # i=6: assistant, i=7-9: tool -> all unsafe
        # Fallback: search backward 9..6, none safe -> return 0
        cut = ctx._find_cut(messages, threshold=8000)
        assert cut == 0


class TestManage:
    def test_under_limit_noop(self):
        counter = HeuristicCounter()
        ctx = ContextManager(counter, MockProvider(), ContextManagerConfig(max_context_tokens=10000))
        messages = [Message.user("short")]
        result = ctx.manage(messages)
        assert result is None
        assert len(messages) == 1

    def test_over_limit_compresses(self):
        """When over threshold, compression is triggered (always, no truncation-only path)."""
        counter = HeuristicCounter()
        mock = MockProvider("摘要")
        ctx = ContextManager(counter, mock, ContextManagerConfig(max_context_tokens=100))
        messages = [Message.user(f"msg {i:02d}") for i in range(20)]
        result = ctx.manage(messages)
        assert result is not None
        assert result["before_count"] == 20
        assert result["after_count"] < 20
        assert mock.last_messages is not None  # provider was called

    def test_compress_uses_provider(self):
        """Compression triggers provider call."""
        counter = HeuristicCounter()
        mock = MockProvider("摘要内容")
        ctx = ContextManager(
            counter, mock, ContextManagerConfig(max_context_tokens=20)
        )
        messages = [Message.user(f"this is a long message number {i} with extra text") for i in range(10)]
        ctx.manage(messages)
        assert mock.last_messages is not None

    def test_compress_summary_has_prefix(self):
        counter = HeuristicCounter()
        mock = MockProvider("这是摘要")
        ctx = ContextManager(
            counter, mock, ContextManagerConfig(max_context_tokens=20)
        )
        messages = [Message.user(f"this is a long message number {i} with extra text") for i in range(10)]
        ctx.manage(messages)
        assert messages[0].content.startswith(SUMMARY_PREFIX)
        assert "这是摘要" in messages[0].content

    def test_manage_returns_action_info(self):
        counter = HeuristicCounter()
        ctx = ContextManager(counter, MockProvider(), ContextManagerConfig(max_context_tokens=100))
        messages = [Message.user(f"msg {i:02d}") for i in range(20)]
        result = ctx.manage(messages)
        assert result is not None
        assert "before_count" in result
        assert "after_count" in result
        assert result["before_count"] > result["after_count"]


class TestValidateConfig:
    def test_default_config_passes(self):
        """Default config: (1-0.6)*1.2 + 0.1 = 0.58 <= 0.60."""
        ctx = ContextManager(HeuristicCounter(), MockProvider())
        assert ctx is not None

    def test_warn_at_over_60_percent(self):
        """compress_ratio=0.55, summary_ratio=0.1: 0.64 -> warn."""
        with pytest.warns(UserWarning):
            ContextManager(
                HeuristicCounter(), MockProvider(),
                ContextManagerConfig(compress_ratio=0.55, summary_ratio=0.1),
            )

    def test_error_at_over_70_percent(self):
        """compress_ratio=0.5, summary_ratio=0.2: 0.80 -> ValueError."""
        with pytest.raises(ValueError):
            ContextManager(
                HeuristicCounter(), MockProvider(),
                ContextManagerConfig(compress_ratio=0.5, summary_ratio=0.2),
            )
