"""Tests for parallel tool execution."""
import pytest, tempfile
from pathlib import Path
from core.tools import tool_registry


class TestParallelTools:
    def test_execute_parallel_basic(self):
        calls = [
            ("get_time", {}),
            ("get_time", {}),
        ]
        results = tool_registry.execute_parallel(calls)
        assert len(results) == 2
        assert all(r["ok"] for r in results)
        assert results[0]["tool"] == "get_time"
        assert "iso" in results[0]["result"]

    def test_execute_parallel_unknown_tool(self):
        calls = [("nonexistent", {})]
        results = tool_registry.execute_parallel(calls)
        assert len(results) == 1
        assert results[0]["ok"] is False
        assert "Unknown tool" in results[0]["error"]

    def test_execute_parallel_mixed(self):
        calls = [
            ("get_time", {}),
            ("nonexistent", {}),
            ("get_time", {}),
        ]
        results = tool_registry.execute_parallel(calls)
        assert len(results) == 3
        assert results[0]["ok"] is True
        assert results[1]["ok"] is False
        assert results[2]["ok"] is True

    def test_execute_parallel_read_files(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content A", encoding="utf-8")
        f2.write_text("content B", encoding="utf-8")
        calls = [
            ("read_file", {"filepath": str(f1)}),
            ("read_file", {"filepath": str(f2)}),
        ]
        results = tool_registry.execute_parallel(calls)
        assert len(results) == 2
        assert all(r["ok"] for r in results), results
