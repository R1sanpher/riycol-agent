"""
Agent Tool-use Framework
=========================
OpenAI-compatible function calling with built-in tools.
Tools are registered with JSON Schema and executed in a sandbox.
"""
import json, time
from pathlib import Path
from typing import Any, Callable
from core.logger import log
from core.config import CFG
from core.vision import tool_describe_image
from core.tool_guard import resolve_path, validate_sql, validate_url, validate_file_size, validate_web_fetch


# ============================================================
# Tool Registry
# ============================================================

class Tool:
    """Tool definition with four core elements per the tool-use specification.

    name_for_human  — human-readable display name (e.g. "Read File")
    name_for_model  — model call identifier (e.g. "read_file")
    description     — what the tool does, for the model (NOT the human)
    parameters      — JSON Schema object describing inputs
    """

    def __init__(self, name: str, description: str, parameters: dict, fn: Callable,
                 name_for_human: str = ""):
        self.name_for_human = name_for_human or name.replace("_", " ").title()
        self.name_for_model = name
        self.description = description
        self.parameters = parameters  # JSON Schema
        self.fn = fn

    # Backward-compat alias
    @property
    def name(self) -> str:
        return self.name_for_model

    @name.setter
    def name(self, val: str):
        self.name_for_model = val

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name_for_model,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def to_dict(self) -> dict:
        """Export all four core elements for human-inspectable tool registry."""
        return {
            "name_for_human": self.name_for_human,
            "name_for_model": self.name_for_model,
            "description_for_model": self.description,
            "parameters": self.parameters,
        }

    def execute(self, arguments: dict) -> str:
        try:
            result = self.fn(**arguments)
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name_for_model] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_schemas(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def list_tools_human(self) -> list[dict]:
        """Export all tools with the four-element specification."""
        return [t.to_dict() for t in self._tools.values()]

    def execute_parallel(self, calls: list[tuple[str, dict]]) -> list[dict]:
        """Execute multiple independent tool calls in parallel.

        Uses ThreadPoolExecutor for I/O-bound tools. Collects exceptions
        without aborting other tools.

        Args:
            calls: list of (tool_name, arguments) tuples

        Returns:
            list of {tool, ok, result, error} dicts (same order)
        """
        import concurrent.futures
        results: list[dict] = [{}] * len(calls)

        def _exec(idx: int, name: str, args: dict) -> tuple[int, dict]:
            tool = self.get(name)
            if not tool:
                return idx, {"tool": name, "ok": False, "error": f"Unknown tool: {name}"}
            try:
                r = tool.execute(args)
                return idx, {"tool": name, "ok": True, "result": r}
            except Exception as e:
                return idx, {"tool": name, "ok": False, "error": str(e)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(_exec, i, name, args): i for i, (name, args) in enumerate(calls)}
            for future in concurrent.futures.as_completed(futures):
                idx, result = future.result()
                results[idx] = result

        return results


# ============================================================
# Built-in Tools
# ============================================================

def _safe_path(filepath: str) -> Path:
    """Resolve and validate path stays within project root."""
    root = CFG.ROOT.resolve()
    p = Path(filepath)
    if not p.is_absolute():
        p = root / p
    p = p.resolve()
    try:
        p.relative_to(root)
    except ValueError:
        raise ValueError(f"Path outside project: {filepath}")
    return p


def tool_read_file(filepath: str, max_lines: int = 200) -> dict:
    """Read a file within the project directory."""
    root = CFG.ROOT.resolve()
    try:
        p = resolve_path(filepath)
    except ValueError as e:
        return {"error": str(e)}
    if not p.exists():
        return {"error": f"File not found: {filepath}"}
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        total = len(lines)
        return {
            "filepath": str(p.relative_to(root)),
            "lines": min(total, max_lines),
            "total_lines": total,
            "content": "\n".join(lines[:max_lines]),
        }
    except Exception as e:
        return {"error": str(e)}


def tool_write_file(filepath: str, content: str, mode: str = "w") -> dict:
    """Write content to a file within the project directory."""
    root = CFG.ROOT.resolve()
    p = _safe_path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"written": str(p.relative_to(root)), "bytes": len(content.encode("utf-8"))}


def tool_search_kb(query: str, top_k: int = 5) -> dict:
    """Search the local knowledge base."""
    try:
        from plugins.server.kb import KnowledgeBase
        kb = KnowledgeBase(docs_dir=str(CFG.DOCS), mode="keyword")
        kb.watch()
        result = kb.query(query, top_k=top_k)
        return {
            "has_result": result["has_result"],
            "sources": result["sources"],
            "context": result["context"][:2000],
        }
    except Exception as e:
        return {"error": str(e)}


def _readonly_authorizer(action_code: int, *args):
    """SQLite authorizer callback: only allow read operations."""
    import sqlite3
    # SQLITE_OK=0, SQLITE_DENY=1, SQLITE_IGNORE=2
    read_ops = (
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE,
        sqlite3.SQLITE_PRAGMA,  # allow PRAGMA for harmless introspection
    )
    if action_code in read_ops:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def tool_db_query(sql: str, limit: int = 20) -> dict:
    """Execute a read-only SQL query on the local database."""
    import sqlite3
    sql_stripped = sql.strip()
    try:
        from core.db import DB
        with DB._lock:
            DB.conn.set_authorizer(_readonly_authorizer)
            try:
                cur = DB.conn.execute(sql_stripped)
                rows = cur.fetchmany(limit)
                cols = [d[0] for d in cur.description] if cur.description else []
                result = {
                    "columns": cols,
                    "row_count": len(rows),
                    "rows": [dict(zip(cols, r)) for r in rows],
                }
            finally:
                DB.conn.set_authorizer(None)
        return result
    except sqlite3.DatabaseError as e:
        return {"error": str(e)}


def tool_get_time() -> dict:
    """Get current server time."""
    now = time.localtime()
    return {
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", now),
        "date": time.strftime("%Y-%m-%d", now),
        "time": time.strftime("%H:%M:%S", now),
        "weekday": time.strftime("%A", now),
    }


def tool_agent_browser(command: str, args: str = "") -> dict:
    """Execute an agent-browser CLI command. Returns the output.
    Use for web navigation, snapshots, clicks, form filling, screenshots.
    Common commands: open <url>, snapshot -i, click @e1, fill @e2 'text', screenshot path.png
    """
    import subprocess
    try:
        cmd = ["agent-browser"]
        cmd.extend(command.split())
        if args:
            cmd.extend(args.split())
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:500],
        }
    except FileNotFoundError:
        return {"error": "agent-browser 未安装。npm install -g agent-browser && agent-browser install"}
    except subprocess.TimeoutExpired:
        return {"error": "命令超时 (>30s)"}
    except Exception as e:
        return {"error": str(e)}


def tool_web_fetch(url: str, max_chars: int = 3000) -> dict:
    """Fetch a web page and return its text content."""
    try:
        url, max_chars, timeout = validate_web_fetch(url, max_chars)
        import requests as _r
        resp = _r.get(url, timeout=timeout, headers={"User-Agent": "RiycolAgent/2.3"})
        resp.raise_for_status()
        text = resp.text[:max_chars]
        # Strip HTML tags crudely
        import re as _re
        text = _re.sub(r"<[^>]+>", " ", text)
        text = _re.sub(r"\s+", " ", text).strip()
        return {"url": url, "status": resp.status_code, "text": text}
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# Global Registry
# ============================================================

tool_registry = ToolRegistry()

_builtin_tools = [
    Tool("read_file", "Read a text file from the project directory",
         {"type": "object", "properties": {
             "filepath": {"type": "string", "description": "Path relative to project root or absolute within project"},
             "max_lines": {"type": "integer", "description": "Max lines to return (default 200)"},
         }, "required": ["filepath"]},
         tool_read_file, name_for_human="Read File"),

    Tool("write_file", "Write content to a file in the project directory",
         {"type": "object", "properties": {
             "filepath": {"type": "string", "description": "Path relative to project root"},
             "content": {"type": "string", "description": "Content to write"},
         }, "required": ["filepath", "content"]},
         tool_write_file, name_for_human="Write File"),

    Tool("search_kb", "Search the local knowledge base for relevant documents",
         {"type": "object", "properties": {
             "query": {"type": "string", "description": "Search query"},
             "top_k": {"type": "integer", "description": "Number of results (default 5)"},
         }, "required": ["query"]},
         tool_search_kb, name_for_human="Search Knowledge Base"),

    Tool("db_query", "Run a read-only SQL query on the local database",
         {"type": "object", "properties": {
             "sql": {"type": "string", "description": "SELECT query to execute"},
             "limit": {"type": "integer", "description": "Max rows (default 20)"},
         }, "required": ["sql"]},
         tool_db_query, name_for_human="Database Query"),

    Tool("get_time", "Get current server date and time",
         {"type": "object", "properties": {}, "required": []},
         tool_get_time, name_for_human="Get Current Time"),

    Tool("web_fetch", "Fetch content from a URL",
         {"type": "object", "properties": {
             "url": {"type": "string", "description": "URL to fetch"},
             "max_chars": {"type": "integer", "description": "Max characters (default 3000)"},
         }, "required": ["url"]},
         tool_web_fetch, name_for_human="Web Fetch"),

    Tool("agent_browser", "Execute browser automation: navigate pages, snapshot elements, click, fill forms, screenshot",
         {"type": "object", "properties": {
             "command": {"type": "string", "description": "agent-browser command (e.g. 'open https://example.com', 'snapshot -i', 'click @e1', 'fill @e2 text', 'screenshot out.png')"},
             "args": {"type": "string", "description": "Additional args (optional)"},
         }, "required": ["command"]},
         tool_agent_browser, name_for_human="Agent Browser"),

    Tool("describe_image", "Describe/analyze an image file (png/jpg/webp)",
         {"type": "object", "properties": {
             "filepath": {"type": "string", "description": "Path to image file"},
             "prompt": {"type": "string", "description": "Question about the image"},
         }, "required": ["filepath"]},
         tool_describe_image, name_for_human="Describe Image"),
]

for t in _builtin_tools:
    tool_registry.register(t)


def get_openai_tools() -> list[dict]:
    return tool_registry.get_schemas()
