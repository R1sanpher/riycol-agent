"""
Model Router — auto-selects between local Qwen and DeepSeek API.
"""
import time
from core.logger import log
from core.retry import CircuitBreaker
from core.config import CFG

# Cache availability check results to avoid HTTP calls on every route()
_avail_cache: dict[str, bool] | None = None
_avail_cache_ts: float = 0
_CACHE_TTL = 30  # seconds

# Circuit breakers per backend
_deepseek_cb = CircuitBreaker("deepseek", failure_threshold=5, recovery_timeout=30)
_ollama_cb = CircuitBreaker("ollama", failure_threshold=3, recovery_timeout=45)
_local_cb = CircuitBreaker("local", failure_threshold=3, recovery_timeout=60)


def get_available_models(force: bool = False) -> dict[str, bool]:
    """Check which models are available. Results cached for _CACHE_TTL seconds."""
    global _avail_cache, _avail_cache_ts
    now = time.time()
    if not force and _avail_cache is not None and (now - _avail_cache_ts) < _CACHE_TTL:
        return _avail_cache.copy()

    available: dict[str, bool] = {}
    # Check Ollama
    try:
        import requests
        resp = requests.get(f"{get_ollama_url()}/api/tags", timeout=2)
        available["ollama"] = resp.status_code == 200
    except Exception:
        available["ollama"] = False
    # Check local via bridge
    try:
        from core.llm_bridge import is_loaded
        available["local"] = is_loaded()
    except Exception:
        available["local"] = False
    # Check DeepSeek
    available["deepseek"] = bool(CFG.DEEPSEEK_KEY)
    # Circuit breaker overrides: open circuit = unavailable
    for backend in ("ollama", "local", "deepseek"):
        cb = get_circuit_breaker(backend)
        if cb and cb.is_open:
            available[backend] = False
            log.info(f"Model '{backend}' marked unavailable (circuit open)")
    if not any(available.values()):
        available["none"] = True  # type: ignore[assignment]

    _avail_cache = available.copy()
    _avail_cache_ts = now
    return available


def get_circuit_breaker(backend: str) -> CircuitBreaker | None:
    cb_map = {"deepseek": _deepseek_cb, "ollama": _ollama_cb, "local": _local_cb}
    return cb_map.get(backend)


def record_backend_success(backend: str):
    cb = get_circuit_breaker(backend)
    if cb:
        cb.record_success()


def record_backend_failure(backend: str):
    cb = get_circuit_breaker(backend)
    if cb:
        cb.record_failure()


def get_ollama_url() -> str:
    return CFG.OLLAMA_URL


def route(task: str, preferred: str = "auto") -> str:
    """
    Route a task to the best available model.

    Returns "ollama", "local", or "deepseek".
    Routing policy (90/10 rule):
      - 90% local: prefer Ollama/local for most tasks
      - 10% deepseek: only route to cloud for complex/long/technical tasks
      - Falls back to any available backend when preferred is unavailable

    The heuristic is only evaluated ONCE (not dead code).
    """
    available = get_available_models()

    if preferred != "auto":
        if available.get(preferred):
            return preferred

    # ── 90/10 routing heuristic ──────────────────────────
    # Check complexity BEFORE defaulting to ollama
    task_lower = task.lower() if task else ""
    is_long = len(task) > 200
    technical_keywords = [
        "代码", "debug", "优化", "算法", "架构", "设计模式",
        "code", "function", "class", "api", "database", "sql",
        "python", "javascript", "rust", "golang", "async",
        "安全", "漏洞", "加密", "性能", "内存", "并发",
    ]
    is_technical = any(kw in task_lower for kw in technical_keywords)
    is_complex = task.count("?") > 2 or task.count("\n") > 3
    needs_deepseek = (is_technical or is_long) and is_complex

    if available.get("ollama"):
        if needs_deepseek and available.get("deepseek"):
            log.info(f"Router: deepseek (technical={is_technical} long={is_long} complex={is_complex})")
            return "deepseek"
        return "ollama"
    if available.get("local"):
        if needs_deepseek and available.get("deepseek"):
            log.info("Router: deepseek (local too weak for complex task)")
            return "deepseek"
        return "local"
    if available.get("deepseek"):
        return "deepseek"

    # No backend available
    log.warn("No models available")
    return "local"
