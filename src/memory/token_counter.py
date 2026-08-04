"""Token counting for context management.

Provides provider-aware token counting so the context manager knows when
to truncate or compress. Priority:

1. AutoTokenizer (HuggingFace) for supported models (Qwen, GLM, DeepSeek,
   Baichuan, Yi, etc.)
2. tiktoken for OpenAI models (accurate, local)
3. chars/4 heuristic fallback for everything else (e.g. Claude)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.llm.types import Message

# Per-message overhead: role markers, delimiters, etc.
_MESSAGE_OVERHEAD = 4


@dataclass(frozen=True)
class SupportedModel:
    """A model family supported by AutoTokenizer.

    Attributes:
        keyword:  Case-insensitive substring to match in the model name.
        hf_repo:  HuggingFace tokenizer repo used to load the tokenizer.
        name:     Human-readable model family name.
    """

    keyword: str
    hf_repo: str
    name: str


# Registry of models supported by AutoTokenizer.
# Order matters: more specific keywords (e.g. "chatglm") should come
# before shorter ones (e.g. "glm") to avoid premature matches.
SUPPORTED_MODELS: list[SupportedModel] = [
    SupportedModel(keyword="qwen", hf_repo="Qwen/Qwen2.5-7B", name="Qwen"),
    SupportedModel(keyword="chatglm", hf_repo="THUDM/chatglm3-6b", name="ChatGLM"),
    SupportedModel(keyword="glm", hf_repo="THUDM/glm-4-9b-chat", name="GLM"),
    SupportedModel(keyword="deepseek", hf_repo="deepseek-ai/deepseek-llm-7b-chat", name="DeepSeek"),
    SupportedModel(keyword="baichuan", hf_repo="baichuan-inc/Baichuan2-7B-Base", name="Baichuan"),
    SupportedModel(keyword="yi-", hf_repo="01-ai/Yi-34B", name="Yi"),
]


def detect_supported_model(model: str) -> str | None:
    """Check if *model* belongs to a supported model family.

    Returns the HuggingFace tokenizer repo name if recognised, or the
    model itself when it already looks like a HF path (contains ``/``).
    Returns ``None`` if the model is not in the supported list.
    """
    model_lower = model.lower()
    for sm in SUPPORTED_MODELS:
        if sm.keyword in model_lower:
            # If the caller already passed a HF path, use it directly.
            if "/" in model:
                return model
            return sm.hf_repo
    return None


class TokenCounter(ABC):
    """Abstract token counter interface."""

    @abstractmethod
    def count_text(self, text: str) -> int:
        """Count tokens in a text string."""
        ...

    def count_messages(self, messages: list[Message]) -> int:
        """Count total tokens across all messages.

        Includes content, tool call metadata, and per-message overhead.
        """
        total = 0
        for msg in messages:
            total += self.count_text(msg.content)
            for tc in msg.tool_calls:
                total += self.count_text(tc.name)
                total += self.count_text(str(tc.arguments))
            if msg.tool_call_id:
                total += self.count_text(msg.tool_call_id)
            total += _MESSAGE_OVERHEAD
        return total


class AutoTokenizerCounter(TokenCounter):
    """Token counter using HuggingFace AutoTokenizer (for supported models).

    Requires the ``transformers`` package (``pip install transformers``).
    Falls back to chars/4 heuristic if the package is missing or the
    tokenizer cannot be loaded.
    """

    def __init__(self, model: str) -> None:
        self._tokenizer = None
        try:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(model)
        except Exception:
            pass

    @property
    def is_available(self) -> bool:
        """Whether the HF tokenizer was successfully loaded."""
        return self._tokenizer is not None

    def count_text(self, text: str) -> int:
        if self._tokenizer is None:
            return max(1, len(text) // 4)
        return len(self._tokenizer.encode(text))


class TiktokenCounter(TokenCounter):
    """Accurate token counter using tiktoken (for OpenAI models).

    Falls back to HeuristicCounter if tiktoken cannot load the encoding
    (e.g., no network access to download the BPE file).
    """

    def __init__(self, model: str = "gpt-4o") -> None:
        import tiktoken

        try:
            try:
                self._encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                self._encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback to heuristic if encoding can't be loaded
            self._encoding = None

    def count_text(self, text: str) -> int:
        if self._encoding is None:
            return max(1, len(text) // 4)
        return len(self._encoding.encode(text))


class HeuristicCounter(TokenCounter):
    """Approximate token counter using chars/4 heuristic (for Claude models)."""

    def count_text(self, text: str) -> int:
        return max(1, len(text) // 4)


def create_token_counter(provider: str, model: str) -> TokenCounter:
    """Factory: return the appropriate TokenCounter for the given provider/model.

    Priority:
      1. AutoTokenizerCounter for supported models (if available)
      2. TiktokenCounter for OpenAI
      3. HeuristicCounter as fallback
    """
    # Check supported models first.
    hf_model = detect_supported_model(model)
    if hf_model is not None:
        counter = AutoTokenizerCounter(hf_model)
        if counter.is_available:
            return counter

    if provider == "openai":
        return TiktokenCounter(model)
    return HeuristicCounter()
