"""LLM Bridge unit tests — 12 tests"""
import json
import pytest
from unittest.mock import patch, MagicMock


class TestOllamaLLM:
    def test_create_returns_callable(self):
        from core.llm_bridge import create_ollama_llm
        fn = create_ollama_llm(model="test")
        assert callable(fn)

    @patch("requests.post")
    def test_non_stream_response(self, mock_post):
        from core.llm_bridge import create_ollama_llm
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"completion_tokens": 3},
        }
        mock_post.return_value = mock_resp

        fn = create_ollama_llm(model="gemma4-fast", base_url="http://localhost:11434")
        result = fn("Hello", max_tokens=50, temperature=0.7)

        assert result["choices"][0]["text"] == "Hello!"
        assert result["usage"]["completion_tokens"] == 3
        args = mock_post.call_args
        assert "/v1/chat/completions" in args[0][0]

    @patch("requests.post")
    def test_payload_structure(self, mock_post):
        from core.llm_bridge import create_ollama_llm
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"completion_tokens": 1},
        }
        mock_post.return_value = mock_resp

        fn = create_ollama_llm(model="gemma4-fast", base_url="http://localhost:11434")
        fn("Test prompt", max_tokens=256, temperature=0.5, stop=["END"])

        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["model"] == "gemma4-fast"
        assert payload["max_tokens"] == 256
        assert payload["temperature"] == 0.5
        assert payload["stop"] == ["END"]
        assert not payload["stream"]

    @patch("requests.post")
    def test_chatml_parsing(self, mock_post):
        """Verify ChatML prompt is parsed into messages."""
        from core.llm_bridge import create_ollama_llm
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hi!"}}],
            "usage": {"completion_tokens": 2},
        }
        mock_post.return_value = mock_resp

        fn = create_ollama_llm(model="test")
        chatml = "<|im_start|>system\nYou are helpful.<|im_end|>\n<|im_start|>user\nHello<|im_end|>\n<|im_start|>assistant\n"
        fn(chatml)

        call_kwargs = mock_post.call_args[1]
        messages = call_kwargs["json"]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    @patch("requests.post")
    def test_plain_text_fallback(self, mock_post):
        """Plain text (no ChatML tags) should be treated as user message."""
        from core.llm_bridge import create_ollama_llm
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hi!"}}],
            "usage": {"completion_tokens": 2},
        }
        mock_post.return_value = mock_resp

        fn = create_ollama_llm(model="test")
        fn("Just plain text, no markup")

        messages = mock_post.call_args[1]["json"]["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Just plain text, no markup"

    @patch("requests.post")
    def test_stream_response(self, mock_post):
        from core.llm_bridge import create_ollama_llm
        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: {"choices":[{"delta":{"content":" world"}}]}',
            b"data: [DONE]",
        ]
        mock_post.return_value = mock_resp

        fn = create_ollama_llm(model="test")
        gen = fn("Hi", stream=True)
        chunks = [c["choices"][0]["text"] for c in gen]
        assert "".join(chunks) == "Hello world"


class TestBridgeState:
    def test_set_get_llm(self):
        from core.llm_bridge import set_llm, get_llm, is_loaded, backend
        set_llm("fake_llm", backend="ollama")
        assert get_llm() == "fake_llm"
        assert is_loaded()
        assert backend() == "ollama"

    def test_is_not_loaded_initially(self):
        from core.llm_bridge import set_llm
        set_llm(None, backend="none")
        from core.llm_bridge import is_loaded
        assert not is_loaded()

    def test_generate_raises_when_not_loaded(self):
        from core.llm_bridge import set_llm
        set_llm(None, backend="none")
        from core.llm_bridge import generate
        with pytest.raises(RuntimeError, match="not loaded"):
            generate("test")

    def test_generate_calls_llm(self):
        from core.llm_bridge import set_llm, generate
        mock_llm = MagicMock()
        mock_llm.return_value = {"choices": [{"text": "ok"}]}
        set_llm(mock_llm, backend="llama-cpp")
        result = generate("prompt", max_tokens=100, temperature=0.5)
        mock_llm.assert_called_once()
        assert result["choices"][0]["text"] == "ok"

    def test_generate_default_stop(self):
        from core.llm_bridge import set_llm, generate
        mock_llm = MagicMock()
        mock_llm.return_value = {"choices": [{"text": "ok"}]}
        set_llm(mock_llm, backend="llama-cpp")
        generate("prompt")
        args, kwargs = mock_llm.call_args
        assert "stop" in kwargs
        assert "<|im_end|>" in kwargs["stop"]
