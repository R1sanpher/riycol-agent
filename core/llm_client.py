"""
LLM Client — abstract call interface for core modules.

Breaks the circular dependency: core/planner.py and core/reflection.py
previously imported plugins.agent.raw_llm_call directly. Now plugins
register themselves via set_llm_call() at import time.
"""
from typing import Callable, Optional

_llm_call_fn: Optional[Callable] = None


def set_llm_call(fn: Callable):
    """Register the LLM call function from plugins layer."""
    global _llm_call_fn
    _llm_call_fn = fn


def llm_call(model: str, system: str, user: str, history: list | None = None,
             temperature: float = 0.3, max_tokens: int = 1024) -> str:
    """Call the registered LLM function. Raises RuntimeError if not registered."""
    if _llm_call_fn is None:
        raise RuntimeError("LLM call function not registered. Import plugins.agent first.")
    return _llm_call_fn(model, system, user, history, temperature, max_tokens)
