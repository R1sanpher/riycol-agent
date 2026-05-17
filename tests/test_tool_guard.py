"""Tests for core/tool_guard.py — Poka-Yoke parameter validation."""
import pytest
from pathlib import Path
from core.tool_guard import resolve_path, validate_sql, validate_url, validate_file_size, validate_web_fetch


class TestPathSafety:
    def test_resolve_relative_path(self):
        p = resolve_path("README.md")
        assert p.exists()
        assert p.name == "README.md"

    def test_resolve_path_outside_project(self):
        with pytest.raises(ValueError, match="outside project"):
            resolve_path("/etc/passwd")

    def test_resolve_auto_complete(self):
        p = resolve_path("CLAUDE")
        assert p.exists()
        assert p.name == "CLAUDE.md"


class TestSQLSafety:
    def test_valid_select(self):
        sql = validate_sql("SELECT * FROM conversations")
        assert "SELECT" in sql

    def test_block_drop(self):
        with pytest.raises(ValueError, match="Write operation"):
            validate_sql("DROP TABLE conversations")

    def test_block_delete(self):
        with pytest.raises(ValueError, match="Write operation"):
            validate_sql("DELETE FROM conversations WHERE id=1")

    def test_block_insert(self):
        with pytest.raises(ValueError, match="Write operation"):
            validate_sql("INSERT INTO conversations VALUES(1,2,3)")

    def test_require_select_valid(self):
        sql = validate_sql("SELECT * FROM conversations WHERE id=1")
        assert "SELECT" in sql

    def test_explain_select_allowed(self):
        sql = validate_sql("EXPLAIN SELECT * FROM conversations")
        assert "EXPLAIN" in sql


class TestURLSafety:
    def test_allowed_domain(self):
        url = validate_url("https://github.com/anthropics/claude-code")
        assert "github.com" in url

    def test_localhost_allowed(self):
        url = validate_url("http://localhost:8000/health")
        assert "localhost" in url

    def test_internal_ip_blocked(self):
        with pytest.raises(ValueError, match="Internal network"):
            validate_url("http://192.168.1.1/admin")

    def test_invalid_url(self):
        with pytest.raises(ValueError, match="Invalid URL"):
            validate_url("not-a-url")


class TestWebFetchGuard:
    def test_valid_params(self):
        url, chars, timeout = validate_web_fetch("https://python.org", 1000, 5)
        assert url == "https://python.org"
        assert chars == 1000
        assert timeout == 5

    def test_max_chars_capped(self):
        _, chars, _ = validate_web_fetch("https://python.org", 99999, 10)
        assert chars == 10000


class TestFileSizeGuard:
    def test_valid_file(self):
        p = validate_file_size("README.md")
        assert p.exists()
