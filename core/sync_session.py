"""
Cross-session state sync engine v2.

Every Claude Code session registers itself, tracks its current task,
and reads what other sessions are doing. Enables:

  - Multi-session task coordination (no duplicate work)
  - Progress tracking across sessions
  - Task handoff: Session A finishes, Session B picks up
  - Auto-injected context via UserPromptSubmit hook

Architecture:
  memory_store("_system", "cross_session_state") ← JSON dict
  └── sessions: {session_id: {task, status, progress, ...}}
  └── handoffs: {task_id: {from, to, result, ...}}
  └── registry: {session_name: session_id, ...}
"""
import json, time, uuid, threading
from typing import Any

SESSION_KEY = "cross_session_state"

_local = threading.local()


def _sid() -> str:
    """Get or create a stable session ID for this process."""
    if not hasattr(_local, "session_id"):
        _local.session_id = f"sess_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    return _local.session_id


def _load() -> dict:
    try:
        from core.memory_store import memory_store
        raw = memory_store.get("_system", SESSION_KEY, "{}")
        return json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        return {}


def _save(state: dict):
    try:
        from core.memory_store import memory_store
        state["_ts"] = time.time()
        memory_store.put("_system", SESSION_KEY, json.dumps(state, ensure_ascii=False), ttl=86400 * 7)
    except Exception:
        pass


# ============================================================
# Session lifecycle
# ============================================================

def register_session(name: str = "", task: str = "", status: str = "idle") -> str:
    """Register this session. Call on startup. Returns session_id."""
    sid = _sid()
    state = _load()
    state.setdefault("sessions", {})
    state["sessions"][sid] = {
        "name": name or sid,
        "task": task[:200],
        "status": status,      # idle | working | blocked | done
        "progress": 0,         # 0-100
        "last_action": "",
        "started": time.time(),
        "updated": time.time(),
    }
    state.setdefault("registry", {})
    state["registry"][name or sid] = sid
    _save(state)
    return sid


def update_session(task: str = "", status: str = "", progress: int = -1, last_action: str = ""):
    """Update current session's state. Only provided fields are changed."""
    sid = _sid()
    state = _load()
    s = state.get("sessions", {}).get(sid, {})
    if not s:
        return
    if task:
        s["task"] = task[:200]
    if status:
        s["status"] = status
    if progress >= 0:
        s["progress"] = min(100, progress)
    if last_action:
        s["last_action"] = last_action[:200]
    s["updated"] = time.time()
    state["sessions"][sid] = s
    _save(state)


def finish_session(result: str = "", handoff_to: str = ""):
    """Mark session as done. Optionally hand off to another session."""
    sid = _sid()
    state = _load()
    s = state.get("sessions", {}).get(sid, {})
    if not s:
        return
    s["status"] = "done"
    s["progress"] = 100
    s["result"] = result[:1000]
    s["updated"] = time.time()
    state["sessions"][sid] = s
    if handoff_to:
        state.setdefault("handoffs", []).append({
            "from": sid,
            "to": handoff_to,
            "task": s.get("task", "")[:200],
            "result": result[:1000],
            "ts": time.time(),
        })
        state["handoffs"] = state["handoffs"][-20:]
    _save(state)


# ============================================================
# Cross-session queries
# ============================================================

def get_active_sessions() -> list[dict]:
    """Return all active (non-done) sessions with their tasks."""
    state = _load()
    now = time.time()
    active = []
    for sid, s in state.get("sessions", {}).items():
        if s["status"] != "done" and (now - s.get("updated", 0)) < 3600:
            s["id"] = sid
            s["is_self"] = (sid == _sid())
            active.append(s)
    return sorted(active, key=lambda x: x["updated"], reverse=True)


def get_pending_handoffs() -> list[dict]:
    """Return handoffs not yet acknowledged."""
    state = _load()
    return [h for h in state.get("handoffs", []) if not h.get("ack")]


def ack_handoff(handoff_index: int):
    """Acknowledge a handoff (mark as received)."""
    state = _load()
    if handoff_index < len(state.get("handoffs", [])):
        state["handoffs"][handoff_index]["ack"] = True
        _save(state)


def get_shared_state() -> dict:
    """Return all shared data visible to other sessions."""
    state = _load()
    return {k: v for k, v in state.items() if not k.startswith("_")}


def snapshot() -> dict:
    """Quick snapshot for monitoring."""
    state = _load()
    sessions = state.get("sessions", {})
    return {
        "total_sessions": len(sessions),
        "active": sum(1 for s in sessions.values() if s["status"] not in ("done", "idle")),
        "handoffs": len(state.get("handoffs", [])),
    }
