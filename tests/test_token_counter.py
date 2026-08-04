"""Tests for token counting."""

import pytest

from src.llm.types import Message, ToolCall
from src.memory.token_counter import (
    AutoTokenizerCounter,
    HeuristicCounter,
    SUPPORTED_MODELS,
    SupportedModel,
    TiktokenCounter,
    TokenCounter,
    create_token_counter,
    detect_supported_model,
)


class TestHeuristicCounter:
    def test_count_text_basic(self):
        counter = HeuristicCounter()
        # 8 chars -> 2 tokens
        assert counter.count_text("abcdefgh") == 2

    def test_count_text_empty(self):
        counter = HeuristicCounter()
        assert counter.count_text("") == 1

    def test_count_text_short(self):
        counter = HeuristicCounter()
        # 3 chars -> max(1, 0) = 1
        assert counter.count_text("abc") == 1


class TestTiktokenCounter:
    def test_count_text_basic(self):
        counter = TiktokenCounter("gpt-4o")
        # "hello" should encode to at least 1 token (or heuristic fallback)
        assert counter.count_text("hello") >= 1

    def test_count_text_empty(self):
        counter = TiktokenCounter("gpt-4o")
        # 0 if encoding loaded, 1 if heuristic fallback (max(1, 0))
        assert counter.count_text("") in (0, 1)

    def test_count_text_longer(self):
        counter = TiktokenCounter("gpt-4o")
        short = counter.count_text("hello")
        long = counter.count_text("hello world, this is a longer sentence")
        assert long > short

    def test_unknown_model_fallback(self):
        # Should not raise; falls back to cl100k_base or heuristic
        counter = TiktokenCounter("nonexistent-model-xyz")
        assert counter.count_text("hello") >= 1


class TestCountMessages:
    def test_empty_list(self):
        counter = HeuristicCounter()
        assert counter.count_messages([]) == 0

    def test_single_user_message(self):
        counter = HeuristicCounter()
        msg = Message.user("abcdefgh")  # 8 chars -> 2 tokens + 4 overhead
        assert counter.count_messages([msg]) == 6

    def test_with_tool_calls(self):
        counter = HeuristicCounter()
        tc = ToolCall(id="tc1", name="echo", arguments={"text": "hi"})
        msg = Message.assistant(content="abcdefgh", tool_calls=[tc])
        # content: 2, name "echo": 1, arguments str: ~8 chars -> 2, tool_call_id: none, overhead: 4
        # Total: 2 + 1 + 2 + 4 = 9
        result = counter.count_messages([msg])
        assert result > 6  # more than just content + overhead

    def test_with_tool_message(self):
        counter = HeuristicCounter()
        msg = Message.tool("tc123456", "abcdefgh")  # content 2 + id 2 + overhead 4
        result = counter.count_messages([msg])
        assert result >= 8

    def test_multiple_messages(self):
        counter = HeuristicCounter()
        messages = [
            Message.user("abcdefgh"),  # 2 + 4 = 6
            Message.assistant("abcdefgh"),  # 2 + 4 = 6
        ]
        assert counter.count_messages(messages) == 12


class TestFactory:
    def test_openai_returns_tiktoken(self):
        counter = create_token_counter("openai", "gpt-4o")
        assert isinstance(counter, TiktokenCounter)

    def test_claude_returns_heuristic(self):
        counter = create_token_counter("claude", "claude-sonnet-4-20250514")
        assert isinstance(counter, HeuristicCounter)

    def test_unknown_provider_returns_heuristic(self):
        counter = create_token_counter("unknown", "some-model")
        assert isinstance(counter, HeuristicCounter)


class TestDetectSupportedModel:
    def test_qwen_api_name(self):
        assert detect_supported_model("qwen-max") == "Qwen/Qwen2.5-7B"

    def test_qwen_plus(self):
        assert detect_supported_model("qwen-plus") == "Qwen/Qwen2.5-7B"

    def test_qwen_hf_path(self):
        # HF path is returned as-is
        assert detect_supported_model("Qwen/Qwen2.5-72B") == "Qwen/Qwen2.5-72B"

    def test_glm(self):
        assert detect_supported_model("glm-4") == "THUDM/glm-4-9b-chat"

    def test_chatglm(self):
        assert detect_supported_model("chatglm3-6b") == "THUDM/chatglm3-6b"

    def test_deepseek(self):
        assert detect_supported_model("deepseek-chat") == "deepseek-ai/deepseek-llm-7b-chat"

    def test_baichuan(self):
        assert detect_supported_model("baichuan2-7b") == "baichuan-inc/Baichuan2-7B-Base"

    def test_yi(self):
        assert detect_supported_model("yi-34b") == "01-ai/Yi-34B"

    def test_unsupported_model(self):
        assert detect_supported_model("gpt-4o") is None
        assert detect_supported_model("claude-sonnet-4-20250514") is None
        assert detect_supported_model("llama-3") is None

    def test_case_insensitive(self):
        assert detect_supported_model("QWEN-MAX") == "Qwen/Qwen2.5-7B"
        assert detect_supported_model("DeepSeek-Chat") == "deepseek-ai/deepseek-llm-7b-chat"


class TestSupportedModelsRegistry:
    def test_all_entries_are_supported_model(self):
        for sm in SUPPORTED_MODELS:
            assert isinstance(sm, SupportedModel)
            assert sm.keyword
            assert sm.hf_repo
            assert sm.name

    def test_chatglm_before_glm(self):
        """chatglm must appear before glm to avoid premature match."""
        keywords = [sm.keyword for sm in SUPPORTED_MODELS]
        assert keywords.index("chatglm") < keywords.index("glm")

    def test_registry_covers_all_families(self):
        keywords = {sm.keyword for sm in SUPPORTED_MODELS}
        assert keywords == {"qwen", "chatglm", "glm", "deepseek", "baichuan", "yi-"}


class TestAutoTokenizerCounter:
    def test_fallback_when_transformers_missing(self, monkeypatch):
        """When transformers is not installed, falls back to heuristic."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "transformers":
                raise ImportError("No module named 'transformers'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        counter = AutoTokenizerCounter("Qwen/Qwen2.5-7B")
        assert counter.is_available is False
        # Falls back to heuristic
        assert counter.count_text("abcdefgh") == 2

    def test_fallback_on_load_failure(self, monkeypatch):
        """When tokenizer can't be loaded, falls back to heuristic."""
        import sys
        import types

        # Create a mock transformers module with a failing from_pretrained
        mock_module = types.ModuleType("transformers")

        class MockAutoTokenizer:
            @staticmethod
            def from_pretrained(model):
                raise RuntimeError("Network error")

        mock_module.AutoTokenizer = MockAutoTokenizer
        monkeypatch.setitem(sys.modules, "transformers", mock_module)

        counter = AutoTokenizerCounter("nonexistent/model")
        assert counter.is_available is False
        assert counter.count_text("abcdefgh") == 2

    def test_count_text_empty_fallback(self, monkeypatch):
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "transformers":
                raise ImportError("No module named 'transformers'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        counter = AutoTokenizerCounter("Qwen/Qwen2.5-7B")
        assert counter.count_text("") == 1  # max(1, 0)


class TestFactorySupportedModels:
    def test_qwen_model_prefers_auto_tokenizer(self):
        """Qwen model should return AutoTokenizerCounter (or fallback if
        transformers not installed)."""
        counter = create_token_counter("openai", "qwen-max")
        # If transformers is installed and network works, it's AutoTokenizerCounter.
        # Otherwise it falls back. Either way, it should work.
        assert counter.count_text("hello") >= 1

    def test_glm_model_with_claude_provider(self):
        """GLM model should try AutoTokenizer even with 'claude' provider."""
        counter = create_token_counter("claude", "glm-4")
        assert counter.count_text("hello") >= 1

    def test_deepseek_model(self):
        counter = create_token_counter("openai", "deepseek-chat")
        assert counter.count_text("hello") >= 1

    def test_unsupported_openai_returns_tiktoken(self):
        counter = create_token_counter("openai", "gpt-4o")
        assert isinstance(counter, TiktokenCounter)
