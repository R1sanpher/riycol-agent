"""
Token counter with multiple backends, auto-selecting the best available.
"""
from core.logger import log

_counter = None
_counter_name = "char_estimate"


def _init():
    global _counter, _counter_name
    # Try tiktoken (DeepSeek/gpt tokenizer)
    try:
        import tiktoken
        _counter = tiktoken.get_encoding("cl100k_base")
        _counter_name = "tiktoken_cl100k"
        return
    except Exception:
        pass
    # Try llama-cpp model tokenizer via bridge
    try:
        from core.llm_bridge import get_llm
        llm = get_llm()
        if llm and hasattr(llm, 'tokenize'):
            _counter = llm
            _counter_name = "llama_cpp"
            return
    except Exception:
        pass
    log.warn("No tokenizer available, using char/4 estimate")


def count(text: str) -> int:
    """Count tokens in text using best available backend."""
    global _counter, _counter_name
    if _counter is None:
        _init()
    if _counter is None:
        return max(1, len(text) // 4)
    try:
        if _counter_name == "tiktoken_cl100k":
            return len(_counter.encode(text))
        elif _counter_name == "llama_cpp":
            return len(_counter.tokenize(text.encode("utf-8") if isinstance(text, str) else text))
    except Exception:
        pass
    return max(1, len(text) // 4)


def count_name() -> str:
    global _counter_name
    if _counter is None:
        _init()
    return _counter_name
