import sqlite3
import time
from pathlib import Path
from threading import Lock
from core.config import CFG


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or str(CFG.DATA / "database.db")
        Path(self.db_path).parent.mkdir(exist_ok=True, parents=True)
        self.conn = sqlite3.connect(
            self.db_path, check_same_thread=False, timeout=5.0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=3000")
        self._lock = Lock()
        self._batch_count = 0
        self._init()

    def _init(self):
        sql = '''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
            source TEXT DEFAULT "", token_count INTEGER DEFAULT 0,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS training_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instruction TEXT NOT NULL, output TEXT NOT NULL, source TEXT DEFAULT "",
            dataset TEXT DEFAULT "default", quality REAL DEFAULT 1.0,
            token_count INTEGER DEFAULT 0, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS knowledge_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT UNIQUE NOT NULL, filename TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 0, indexed_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);
        CREATE INDEX IF NOT EXISTS idx_conv_created ON conversations(created_at);
        CREATE INDEX IF NOT EXISTS idx_samples_dataset ON training_samples(dataset);
        CREATE INDEX IF NOT EXISTS idx_samples_quality ON training_samples(quality);
        '''
        self.conn.executescript(sql)
        self.conn.commit()

    def begin_batch(self):
        """Start batch mode — commits are deferred until end_batch()."""
        self._batch_count += 1

    def end_batch(self):
        """End batch mode and commit all pending changes."""
        if self._batch_count > 0:
            self._batch_count -= 1
        if self._batch_count == 0:
            with self._lock:
                self.conn.commit()

    def add_msg(self, sid, role, content, source="", tokens=0):
        with self._lock:
            self.conn.execute(
                "INSERT INTO conversations VALUES(NULL,?,?,?,?,?,?)",
                (sid, role, content, source, tokens, time.time()))
            if self._batch_count == 0:
                self.conn.commit()

    def add_sample(self, instruction, output, source="", dataset="default",
                   quality=1.0, tokens=0):
        with self._lock:
            self.conn.execute(
                "INSERT INTO training_samples VALUES(NULL,?,?,?,?,?,?,?)",
                (instruction, output, source, dataset, quality, tokens, time.time()))
            if self._batch_count == 0:
                self.conn.commit()

    def get_samples(self, dataset="default", limit=5000, min_score=0.0):
        if dataset is None or dataset == "all":
            return [dict(r) for r in self.conn.execute(
                "SELECT * FROM training_samples WHERE quality>=? ORDER BY id ASC LIMIT ?",
                (min_score, limit)).fetchall()]
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM training_samples WHERE dataset=? AND quality>=? ORDER BY id ASC LIMIT ?",
            (dataset, min_score, limit)).fetchall()]

    def stats(self):
        return {
            "messages": self.conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
            "sessions": self.conn.execute("SELECT COUNT(DISTINCT session_id) FROM conversations").fetchone()[0],
            "samples": self.conn.execute("SELECT COUNT(*) FROM training_samples").fetchone()[0],
            "docs": self.conn.execute("SELECT COUNT(*) FROM knowledge_docs").fetchone()[0],
        }

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


DB = Database()
