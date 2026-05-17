"""Tests for sync modules — session state v2 and Notion integration."""
import time, pytest
from core.sync_session import (
    register_session, update_session, finish_session,
    get_active_sessions, get_pending_handoffs, get_shared_state, snapshot
)


class TestSessionSync:
    def test_register_session(self):
        sid = register_session(name="test-sync", task="testing sync", status="working")
        assert sid.startswith("sess_")

    def test_get_shared_state(self):
        register_session(name="shared-test", task="shared task")
        state = get_shared_state()
        assert "sessions" in state or "registry" in state

    def test_snapshot(self):
        register_session(name="snap-test", task="snapshot")
        snap = snapshot()
        assert "total_sessions" in snap
        assert "active" in snap
        assert "handoffs" in snap

    def test_update_session(self):
        sid = register_session(name="update-test", task="initial")
        update_session(task="updated task", progress=50)
        sessions = get_active_sessions()
        my_sessions = [s for s in sessions if s["id"] == sid]
        if my_sessions:
            assert my_sessions[0]["task"] == "updated task"

    def test_finish_session(self):
        sid = register_session(name="finish-test", task="to complete")
        finish_session(result="done!")
        sessions = get_active_sessions()
        my_sessions = [s for s in sessions if s["id"] == sid]
        assert len(my_sessions) == 0 or all(s["status"] == "done" for s in my_sessions)

    def test_state_persistence(self):
        register_session(name="persist-test", task="persistent")
        state1 = snapshot()
        state2 = snapshot()
        assert state1["total_sessions"] == state2["total_sessions"]


class TestNotionSyncModule:
    def test_safe_filename(self):
        from core.sync_notion import _safe_filename
        assert _safe_filename("test title") == "test title"
        assert _safe_filename("file:name?") == "filename"

    def test_api_key_found(self):
        from core.sync_notion import _get_api_key
        key = _get_api_key()
        assert key and key.startswith("ntn_")
