"""Context manager -- truncation and compression of conversation history.

When the conversation grows too long for the LLM's context window, the
context manager kicks in:

1. **Cut**: find a safe cut point at ``compress_ratio`` position (default 60%).
   Messages before the cut are "old" (to be summarized); messages after are
   "recent" (to be kept). Recent messages are limited to
   ``(1 - compress_ratio) * 1.2 * threshold`` tokens.

2. **Compress**: summarize old messages using the LLM. The summary prompt
   limits output to ``summary_ratio * threshold`` tokens (default 10%).

3. **Post-truncate**: if the result still exceeds threshold, drop the oldest
   non-summary messages (preserving the summary at index 0).

All operations modify the message list **in-place** to avoid recompressing
the same messages on every iteration.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

from src.llm.base import LLMProvider
from src.llm.types import Message
from src.memory.token_counter import TokenCounter

# Prefix for summary messages inserted by compression.
SUMMARY_PREFIX = "[对话摘要]"

# Max characters of tool result content included in the summary prompt.
_MAX_TOOL_RESULT_IN_SUMMARY = 500

# Extra space multiplier for recent messages limit.
_CUT_MARGIN = 1.2


@dataclass
class ContextManagerConfig:
    """Configuration for context management."""

    max_context_tokens: int = 100_000
    compression_trigger_ratio: float = 0.8  # trigger at 80% of max
    compress_ratio: float = 0.6  # cut at 60% position
    summary_ratio: float = 0.1  # summary <= 10% of threshold


def _validate_config(config: ContextManagerConfig) -> None:
    """Validate compression ratio configuration.

    Checks that ``(1 - compress_ratio) * 1.2 + summary_ratio`` is within
    acceptable bounds:
    - <= 0.60: OK (default: 0.48 + 0.10 = 0.58)
    - 0.60 ~ 0.70: warn
    - > 0.70: raise ValueError
    """
    recent_limit = (1 - config.compress_ratio) * _CUT_MARGIN
    total = recent_limit + config.summary_ratio
    if total > 0.7:
        raise ValueError(
            f"配置错误：(1 - compress_ratio) * 1.2 + summary_ratio = {total:.2f} > 0.70，"
            f"请减小 compress_ratio 或 summary_ratio"
        )
    if total > 0.6:
        warnings.warn(
            f"配置警告：(1 - compress_ratio) * 1.2 + summary_ratio = {total:.2f} > 0.60，"
            f"压缩后剩余空间较少"
        )


class ContextManager:
    """Manages conversation context by truncating or compressing old messages."""

    def __init__(
        self,
        token_counter: TokenCounter,
        provider: LLMProvider,
        config: ContextManagerConfig | None = None,
    ) -> None:
        self._counter = token_counter
        self._provider = provider
        self._config = config or ContextManagerConfig()
        _validate_config(self._config)

    def manage(self, messages: list[Message]) -> dict | None:
        """Compress messages in-place if over context limit.

        Returns a dict with action info if action was taken, None otherwise.
        """
        threshold = int(
            self._config.max_context_tokens * self._config.compression_trigger_ratio
        )
        token_count = self._counter.count_messages(messages)

        if token_count <= threshold:
            return None

        before = len(messages)

        # Compress: cut at compress_ratio, summarize old messages.
        compressed = self._compress(messages, threshold)
        messages[:] = compressed

        # Post-truncate: if still over threshold, preserve summary (messages[0])
        # and drop oldest non-summary messages.
        while len(messages) > 1 and self._counter.count_messages(messages) > threshold:
            del messages[1]

        return {
            "action": "managed",
            "before_count": before,
            "after_count": len(messages),
        }

    def _is_safe_cut(self, messages: list[Message], i: int) -> bool:
        """Check if cutting at index i (dropping messages[:i]) is safe.

        A cut is safe only when the first retained message (messages[i])
        is a user message -- this ensures:
        - Conversation turns start at user boundaries (semantic completeness).
        - Tool-call/result pairs are never split (tool results are not user).
        - The retained list starts with a user message (required by Claude API).
        """
        if i == 0 or i >= len(messages):
            return True
        return messages[i].role == "user"

    def _find_cut(self, messages: list[Message], threshold: int) -> int:
        """Find a safe cut point at or after compress_ratio position.

        Ensures recent messages (messages[cut:]) fit within
        ``threshold * (1 - compress_ratio) * _CUT_MARGIN`` tokens.

        Returns 0 if no safe cut found.
        """
        n = len(messages)
        if n < 2:
            return 0
        start = int(n * self._config.compress_ratio)
        limit_tokens = int(
            threshold * (1 - self._config.compress_ratio) * _CUT_MARGIN
        )

        # Search forward for safe cut where recent <= limit.
        for i in range(start, n):
            if not self._is_safe_cut(messages, i):
                continue
            recent_tokens = self._counter.count_messages(messages[i:])
            if recent_tokens <= limit_tokens:
                return i

        # Fallback: use the last safe cut (fewest recent messages).
        for i in range(n - 1, start - 1, -1):
            if self._is_safe_cut(messages, i):
                return i
        return 0

    def _compress(self, messages: list[Message], threshold: int) -> list[Message]:
        """Cut and summarize old messages. Returns a new list."""
        cut = self._find_cut(messages, threshold)
        if cut == 0:
            return messages

        old_messages = messages[:cut]
        recent_messages = messages[cut:]

        max_summary_tokens = int(threshold * self._config.summary_ratio)
        summary = self._summarize(old_messages, max_summary_tokens)
        summary_msg = Message.user(f"{SUMMARY_PREFIX}\n{summary}")

        return [summary_msg] + recent_messages

    def _summarize(self, messages: list[Message], max_tokens: int) -> str:
        """Use the LLM to generate a summary of the given messages."""
        prompt_parts = ["请总结以下对话的要点：\n"]
        for msg in messages:
            if msg.role == "user":
                prompt_parts.append(f"[用户]: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"[助手]: {msg.content}")
                for tc in msg.tool_calls:
                    prompt_parts.append(f"  (工具调用: {tc.name})")
            elif msg.role == "tool":
                content = msg.content
                if len(content) > _MAX_TOOL_RESULT_IN_SUMMARY:
                    content = content[:_MAX_TOOL_RESULT_IN_SUMMARY] + "..."
                prompt_parts.append(f"[工具结果]: {content}")

        prompt = "\n".join(prompt_parts)
        response = self._provider.chat(
            messages=[Message.user(prompt)],
            system=(
                "你是一个对话摘要助手。请总结对话要点，要求：\n"
                "1. 保持时间顺序\n"
                "2. 已完成的内容简短总结\n"
                "3. 保留关键信息、决策和上下文\n"
                f"4. 由于长度限制（约{max_tokens} tokens），可以丢弃早期非关键内容"
            ),
        )
        return response.content
