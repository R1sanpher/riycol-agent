"""
Skill Database — indexes and queries project skills with metadata.
Built-in skills are auto-discovered from skills/ directory.
"""
import json, time, re
from pathlib import Path
from typing import Any
from core.logger import log


class SkillRegistry:
    """Searchable skill index backed by DB and KB."""

    def __init__(self, db=None):
        if db is None:
            from core.db import DB
            db = DB
        self._db = db
        self._ensure_table()

    def _ensure_table(self):
        self._db.conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_registry (
                name TEXT PRIMARY KEY,
                category TEXT NOT NULL DEFAULT 'general',
                version TEXT DEFAULT '1.0',
                description TEXT,
                tags TEXT,
                source_path TEXT,
                indexed_at REAL NOT NULL
            )
        """)
        self._db.conn.commit()

    def index_skill(self, name: str, category: str, description: str,
                    tags: list[str] | None = None, source_path: str = "",
                    version: str = "1.0"):
        tag_str = ",".join(tags) if tags else ""
        self._db.conn.execute(
            "INSERT OR REPLACE INTO skill_registry VALUES(?,?,?,?,?,?,?)",
            (name, category, version, description, tag_str, source_path, time.time()))
        self._db.conn.commit()

    def discover(self):
        """Auto-discover all skills from skills/ directory."""
        skills_dir = Path(__file__).parent.parent / "skills"
        if not skills_dir.exists():
            log.warn(f"Skills dir not found: {skills_dir}")
            return []

        found = []
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                content = skill_md.read_text(encoding="utf-8")
                meta = self._parse_frontmatter(content)
                name = meta.get("name", skill_dir.name)
                desc = meta.get("description", content.split("\n")[0].lstrip("# "))
                tags = meta.get("tags", [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",")]

                category = self._infer_category(name, content)
                self.index_skill(name, category, desc, tags,
                                 str(skill_dir.relative_to(skills_dir.parent)))
                found.append(name)
                log.info(f"Skill indexed: {name}")
            except Exception as e:
                log.warn(f"Skill index failed for {skill_dir}: {e}")

        return found

    def _parse_frontmatter(self, content: str) -> dict[str, Any]:
        """Extract YAML-style frontmatter from markdown."""
        if not content.startswith("---"):
            return {}
        end = content.find("---", 3)
        if end == -1:
            return {}
        fm_text = content[3:end].strip()
        meta: dict[str, Any] = {}
        for line in fm_text.split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if v.startswith("[") and v.endswith("]"):
                    v = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",")]
                meta[k] = v
        return meta

    def _infer_category(self, name: str, content: str) -> str:
        cats = {
            "self-improvement": "meta",
            "agent-browser": "tool",
            "agent browser": "tool",
            "memory-palace": "creative",
            "self-critique": "thinking",
            "title-alchemist": "creative",
            "browser": "tool",
        }
        name_lower = name.lower()
        if "browser" in name_lower:
            return "tool"
        if "improve" in name_lower or "learning" in name_lower:
            return "meta"
        return cats.get(name_lower, "general")

    def search(self, query: str) -> list[dict]:
        """Search skills by name, description, or tags."""
        pattern = f"%{query}%"
        rows = self._db.conn.execute(
            "SELECT * FROM skill_registry WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?",
            (pattern, pattern, pattern)).fetchall()
        return [dict(r) for r in rows]

    def list_all(self, category: str = None) -> list[dict]:
        if category:
            rows = self._db.conn.execute(
                "SELECT * FROM skill_registry WHERE category=? ORDER BY name", (category,)).fetchall()
        else:
            rows = self._db.conn.execute(
                "SELECT * FROM skill_registry ORDER BY category, name").fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        total = self._db.conn.execute("SELECT COUNT(*) FROM skill_registry").fetchone()[0]
        cats = self._db.conn.execute(
            "SELECT category, COUNT(*) as cnt FROM skill_registry GROUP BY category"
        ).fetchall()
        return {"total_skills": total, "categories": {r[0]: r[1] for r in cats}}


skill_registry = SkillRegistry()
