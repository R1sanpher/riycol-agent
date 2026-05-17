"""
LLM Bridge — clean interface to local model.
============================================
Supports: llama-cpp-python (GGUF) and Ollama HTTP API.
Handler sets the reference; Agent/tools/router read via get_llm().
"""
import json
from typing import Any

_llm: Any = None
_llm_backend: str = "none"  # "llama-cpp" | "ollama" | "none"


def set_llm(llm: Any, backend: str = "llama-cpp"):
    """Called by handler after model loads."""
    global _llm, _llm_backend
    _llm = llm
    _llm_backend = backend


def get_llm() -> Any | None:
    """Get the current local model instance, or None."""
    return _llm


def is_loaded() -> bool:
    return _llm is not None


def backend() -> str:
    return _llm_backend


def generate(prompt: str, max_tokens: int = 512, temperature: float = 0.7,
             stop: list[str] | None = None, stream: bool = False) -> Any:
    """Generate text from the local model. Returns dict or iterator."""
    llm = get_llm()
    if llm is None:
        raise RuntimeError("Local model not loaded")
    if stop is None:
        stop = ["<|im_end|>"]
    return llm(prompt, max_tokens=max_tokens, temperature=temperature,
               stop=stop, stream=stream)


def create_ollama_llm(model: str = "gemma4-e4b",
                      base_url: str = "http://localhost:11434"):
    """Create an llm() callable backed by Ollama OpenAI-compatible API.

    Parses ChatML prompt into messages, calls /v1/chat/completions,
    and returns results in llama-cpp-compatible format:
        llm(prompt, max_tokens=512, temperature=0.7, stop=[...], stream=False)
    """
    import re as _re
    import requests as _r

    _CHATML_RE = _re.compile(
        r"<\|im_start\|>(\w+)\n(.*?)<\|im_end\|>", _re.DOTALL)

    def _parse_chatml(prompt: str) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        for role, content in _CHATML_RE.findall(prompt):
            content = content.strip()
            if role == "assistant" and not content:
                continue  # Skip trailing assistant prompt
            if role in ("system", "user", "assistant"):
                msgs.append({"role": role, "content": content})
        # If parsing failed, treat whole prompt as user message
        if not msgs:
            msgs = [{"role": "user", "content": prompt.strip()}]
        return msgs

    def _ollama_llm(prompt: str, max_tokens: int = 512, temperature: float = 0.7,
                    stop: list[str] | None = None, stream: bool = False) -> Any:
        messages = _parse_chatml(prompt)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if stop:
            payload["stop"] = stop

        if stream:
            resp = _r.post(
                f"{base_url}/v1/chat/completions", json=payload,
                stream=True, timeout=300)
            resp.raise_for_status()

            def _stream_gen():
                for line in resp.iter_lines():
                    line = line.decode().strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if choices and choices[0].get("delta", {}).get("content"):
                                yield {"choices": [{"text": choices[0]["delta"]["content"]}]}
                        except json.JSONDecodeError:
                            continue
            return _stream_gen()
        else:
            resp = _r.post(
                f"{base_url}/v1/chat/completions", json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            tokens = data.get("usage", {}).get("completion_tokens", 0)
            return {
                "choices": [{"text": text}],
                "usage": {"completion_tokens": tokens},
            }

    return _ollama_llm
