"""
Persistent key-value memory store backed by SQLite.
Survives restarts. Used by Agent to persist conversation history and context.

v2: TTL expiry, schema migration, optional vector store integration.
"""
import json, time
from typing import Any
from core.logger import log


class MemoryStore:
    def __init__(self, db=None, vector_store=None):
        """Pass a Database instance for test isolation, or None to use global DB.

        vector_store: optional MemoryVectorStore for semantic search.
        """
        self._db = db
        if self._db is None:
            from core.db import DB
            self._db = DB
        self._vector = vector_store
        self._ensure_table()
        self._migrate()

    def _ensure_table(self):
        self._db.conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_memory (
                agent_name TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (agent_name, key)
            )
        """)
        self._db.conn.commit()

    def _migrate(self):
        """Add ttl column if missing (v2 migration)."""
        cols = self._db.conn.execute("PRAGMA table_info(agent_memory)").fetchall()
        if not any(c[1] == "ttl" for c in cols):
            self._db.conn.execute(
                "ALTER TABLE agent_memory ADD COLUMN ttl REAL DEFAULT NULL"
            )
            self._db.conn.commit()
            log.info("MemoryStore: added ttl column (v2 migration)")

    def _expire(self):
        """Remove entries where (updated_at + ttl) < now."""
        self._db.conn.execute(
            "DELETE FROM agent_memory WHERE ttl IS NOT NULL AND (updated_at + ttl) < ?",
            (time.time(),)
        )
        self._db.conn.commit()

    def gc(self) -> int:
        """Remove all expired entries. Returns count removed."""
        before = self._db.conn.execute("SELECT COUNT(*) FROM agent_memory").fetchone()[0]
        self._expire()
        after = self._db.conn.execute("SELECT COUNT(*) FROM agent_memory").fetchone()[0]
        return before - after

    def put(self, agent_name: str, key: str, value: Any, ttl: float | None = None):
        """Store value with optional TTL in seconds. None = no expiry."""
        data = json.dumps(value, ensure_ascii=False)
        self._db.conn.execute(
            "INSERT OR REPLACE INTO agent_memory VALUES(?,?,?,?,?)",
            (agent_name, key, data, time.time(), ttl))
        self._db.conn.commit()
        if self._vector is not None:
            try:
                self._vector.add(agent_name, key, str(value))
            except Exception:
                pass

    def get(self, agent_name: str, key: str, default: Any = None) -> Any:
        self._expire()
        row = self._db.conn.execute(
            "SELECT value FROM agent_memory WHERE agent_name=? AND key=?",
            (agent_name, key)).fetchone()
        if row:
            return json.loads(row[0])
        return default

    def delete(self, agent_name: str, key: str):
        self._db.conn.execute(
            "DELETE FROM agent_memory WHERE agent_name=? AND key=?",
            (agent_name, key))
        self._db.conn.commit()

    def list_keys(self, agent_name: str) -> list[str]:
        self._expire()
        rows = self._db.conn.execute(
            "SELECT key FROM agent_memory WHERE agent_name=? ORDER BY updated_at DESC",
            (agent_name,)).fetchall()
        return [r[0] for r in rows]

    def clear_agent(self, agent_name: str):
        self._db.conn.execute("DELETE FROM agent_memory WHERE agent_name=?", (agent_name,))
        self._db.conn.commit()

    def stats(self) -> dict:
        self._expire()
        total = self._db.conn.execute("SELECT COUNT(*) FROM agent_memory").fetchone()[0]
        agents = self._db.conn.execute(
            "SELECT agent_name, COUNT(*) as cnt FROM agent_memory GROUP BY agent_name"
        ).fetchall()
        return {"total_entries": total, "agents": {r[0]: r[1] for r in agents}}

    def semantic_search(self, agent_name: str, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search across agent memory. Requires vector_store configured."""
        if self._vector is None:
            return []
        return self._vector.query(agent_name, query, top_k)


# Global singleton
try:
    from core.memory_vector import MemoryVectorStore
    memory_store = MemoryStore(vector_store=MemoryVectorStore())
except Exception:
    memory_store = MemoryStore()
