"""API endpoint unit tests"""
import io
import pytest
from unittest.mock import patch, MagicMock

class TestHandlerRoutes:
    """Route dispatch tests"""
    @pytest.fixture
    def handler(self):
        from plugins.server.handler import Handler
        h = Handler.__new__(Handler)
        h.command = "GET"
        h.path = "/"; h.headers = {}
        h.rfile = io.BytesIO(b"{}")
        h.wfile = io.BytesIO()
        h.send_response = MagicMock()
        h.send_header = MagicMock()
        h.end_headers = MagicMock()
        h.wfile.write = MagicMock()
        h._json = MagicMock()
        h.send_error = MagicMock()
        return h
    def test_health(self, handler):
        handler.path = "/health"
        handler.do_GET()
        handler._json.assert_called()
    def test_ping(self, handler):
        """AC1+AC3: GET /ping -> 200, pong:true, ISO 8601 timestamp, metrics unchanged"""
        from plugins.server.handler import metrics
        from datetime import date
        before = metrics.requests_total
        handler.path = "/ping"
        handler.do_GET()
        data = handler._json.call_args[0][0]
        assert data["pong"] is True
        assert "timestamp" in data
        ts = data["timestamp"]
        assert "T" in ts, "timestamp must be ISO 8601 format"
        # date part must parse as valid date
        date.fromisoformat(ts.split("T")[0])
        # metrics must not increment for liveness probe
        assert metrics.requests_total == before

    def test_ping_no_auth_required(self, handler, monkeypatch):
        """AC2: GET /ping is public, returns 200 even with API_KEY configured"""
        monkeypatch.setenv("API_KEY", "test-secret-key")
        handler.path = "/ping"
        handler.do_GET()
        handler._json.assert_called_once()
        data = handler._json.call_args[0][0]
        assert data["pong"] is True
        assert "timestamp" in data

    def test_root(self, handler):
        with patch("plugins.server.handler.Handler._serve_file") as m:
            handler.path = "/"
            handler.do_GET()
            m.assert_called_with("index.html")
    def test_404(self, handler):
        handler.path = "/unknown"
        handler.do_GET()
        handler.send_error.assert_called_with(404)

class TestKBEndpoints:
    """KB API tests"""
    @pytest.fixture
    def handler(self):
        from plugins.server.handler import Handler
        h = Handler.__new__(Handler)
        h.command = "GET"
        h.path = "/"
        h.headers = {"Content-Length": "2"}
        h.client_address = ("127.0.0.1", 12345)
        h.rfile = io.BytesIO(b"{}")
        h.wfile = io.BytesIO()
        h.send_response = MagicMock()
        h.send_header = MagicMock()
        h.end_headers = MagicMock()
        h.wfile.write = MagicMock()
        h._json = MagicMock()
        return h
    def test_no_filepath(self, handler):
        handler._kb_upload({"content": "test"})
        args = handler._json.call_args
        assert args[0][0]["error"] == "filepath required"
    def test_no_text(self, handler):
        handler._kb_add_text({"filename": "test.txt"})
        args = handler._json.call_args
        assert args[0][0]["error"] == "text required"
    def test_no_filename(self, handler):
        handler._kb_delete({})
        args = handler._json.call_args
        assert args[0][0]["error"] == "filename required"
    def test_large_request(self, handler):
        handler.headers["Content-Length"] = str(50*1024*1024)
        handler.do_POST()
        args = handler._json.call_args
        assert args[0][0]["error"] == "Request too large"

class TestSecurity:
    """Security tests"""
    def test_sql_injection(self, tmp_path):
        from core.db import Database
        d = Database(db_path=str(tmp_path / "test.db"))
        d.add_msg("'; DROP TABLE; --", "user", "test")
        stats = d.stats(); d.close()
        assert stats["messages"] >= 0

class TestErrorHandling:
    """Error handling tests"""
    @pytest.fixture
    def handler(self):
        from plugins.server.handler import Handler, llm
        h = Handler.__new__(Handler)
        h.command = "GET"
        h.path = "/"
        h.headers = {"Content-Length": "2"}
        h.client_address = ("127.0.0.1", 12345)
        h.rfile = io.BytesIO(b"{}")
        h.wfile = io.BytesIO()
        h.send_response = MagicMock()
        h.send_header = MagicMock()
        h.end_headers = MagicMock()
        h.wfile.write = MagicMock()
        h._json = MagicMock()
        # mock llm to not be None for prompt check
        return h
    def test_unknown_route(self, handler):
        handler.path = "/nonexistent"
        handler.do_POST()
        args = handler._json.call_args
        assert args[0][0]["error"] == "not found"
    def test_no_prompt(self, handler):
        # Mock llm so the handler can proceed past the None check
        with patch("plugins.server.handler.llm", MagicMock()):
            handler._handle_chat({})
            args = handler._json.call_args
            assert args[0][0]["error"] == "prompt required"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
