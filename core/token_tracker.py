"""
token_tracker.py — Centralized per-call and cumulative token consumption tracker.

Thread-safe singleton. Records every LLM call with model, source, and token counts.
Exposes snapshot() for real-time monitoring via API or CLI.

Usage:
    from core.token_tracker import tracker
    tracker.record("deepseek", "agent", prompt_tokens=150, completion_tokens=50)
    stats = tracker.snapshot(limit=50)
"""

import json, time, threading
from pathlib import Path
from typing import Any

DEEPSEEK_INPUT_COST_PER_M = 0.27
DEEPSEEK_OUTPUT_COST_PER_M = 1.10


class TokenRecord:
    """Single LLM call record — immutable after creation."""
    __slots__ = ("ts", "model", "source", "prompt_tokens", "completion_tokens",
                 "total_tokens", "cost")

    def __init__(self, model: str, source: str, prompt_tokens: int,
                 completion_tokens: int):
        self.ts = time.time()
        self.model = model
        self.source = source
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        self.cost = self._calc_cost()

    def _calc_cost(self) -> float:
        if self.model == "deepseek":
            return (self.prompt_tokens / 1_000_000 * DEEPSEEK_INPUT_COST_PER_M +
                    self.completion_tokens / 1_000_000 * DEEPSEEK_OUTPUT_COST_PER_M)
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.ts,
            "time_str": time.strftime("%H:%M:%S", time.localtime(self.ts)),
            "model": self.model,
            "source": self.source,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": round(self.cost, 6),
        }


class TokenTracker:
    """Thread-safe singleton for tracking token consumption across all LLM calls.

    Persists to a JSON file so external processes (e.g. desktop monitor)
    can read the data without needing the server.
    """

    def __init__(self, max_records: int = 1000, persist_path: str | None = None):
        self._records: list[TokenRecord] = []
        self._max_records = max_records
        self._lock = threading.Lock()
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path:
            self._load()

    def _load(self):
        """Load records from the persist file."""
        try:
            if self._persist_path.exists():
                raw = json.loads(self._persist_path.read_text("utf-8"))
                for item in raw:
                    rec = TokenRecord.__new__(TokenRecord)
                    for k in ("ts", "model", "source", "prompt_tokens",
                              "completion_tokens", "total_tokens", "cost"):
                        setattr(rec, k, item[k])
                    self._records.append(rec)
        except Exception:
            pass  # Corrupted file — start fresh

    def _save(self):
        """Write all records to the persist file."""
        if not self._persist_path:
            return
        try:
            raw = [{"ts": r.ts, "model": r.model, "source": r.source,
                     "prompt_tokens": r.prompt_tokens,
                     "completion_tokens": r.completion_tokens,
                     "total_tokens": r.total_tokens, "cost": r.cost}
                    for r in self._records]
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._persist_path.write_text(json.dumps(raw, ensure_ascii=False), "utf-8")
        except Exception:
            pass

    def record(self, model: str, source: str,
               prompt_tokens: int, completion_tokens: int):
        """Record a single LLM call's token usage.

        Args:
            model: Model backend name (e.g. "deepseek", "ollama", "local", "mock")
            source: System component (e.g. "server", "agent", "telegram", "planner")
            prompt_tokens: Input token count (>= 0)
            completion_tokens: Output token count (>= 0)
        """
        if prompt_tokens < 0 or completion_tokens < 0:
            return
        rec = TokenRecord(model, source, prompt_tokens, completion_tokens)
        with self._lock:
            self._records.append(rec)
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
        self._save()

    def snapshot(self, limit: int = 100) -> dict[str, Any]:
        """Return cumulative stats + most recent records (newest first)."""
        with self._lock:
            records = list(self._records)

        total_prompt = sum(r.prompt_tokens for r in records)
        total_completion = sum(r.completion_tokens for r in records)
        total_cost = sum(r.cost for r in records)
        call_count = len(records)

        # Per-source breakdown
        by_source: dict[str, dict[str, int | float]] = {}
        for r in records:
            s = by_source.setdefault(r.source, {"calls": 0, "prompt": 0, "completion": 0})
            s["calls"] += 1
            s["prompt"] += r.prompt_tokens
            s["completion"] += r.completion_tokens

        # Per-model breakdown
        by_model: dict[str, dict[str, int | float]] = {}
        for r in records:
            s = by_model.setdefault(r.model, {"calls": 0, "prompt": 0, "completion": 0, "cost": 0.0})
            s["calls"] += 1
            s["prompt"] += r.prompt_tokens
            s["completion"] += r.completion_tokens
            s["cost"] = round(s["cost"] + r.cost, 4)

        recent = [r.to_dict() for r in records[-limit:]]
        recent.reverse()  # newest first

        return {
            "total": {
                "calls": call_count,
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "total_tokens": total_prompt + total_completion,
                "cost": round(total_cost, 4),
            },
            "by_source": by_source,
            "by_model": by_model,
            "recent": recent,
        }

    def reset(self):
        """Clear all recorded data."""
        with self._lock:
            self._records.clear()
        if self._persist_path:
            try:
                self._persist_path.unlink(missing_ok=True)
            except Exception:
                pass


# Global singleton — import this everywhere
tracker = TokenTracker(persist_path=str(Path(__file__).parent.parent / "data" / "token_tracker.json"))
