"""Batch ingest project documentation into knowledge base."""
import sys
sys.path.insert(0, ".")

from pathlib import Path
from core.config import CFG
from plugins.server.kb import KnowledgeBase

def main():
    kb = KnowledgeBase(docs_dir=str(CFG.DOCS), mode="keyword")

    # Copy key project files into docs_dir for KB indexing
    source_dirs = [
        (".", ["CLAUDE.md", "README.md", "pyproject.toml"]),
        (".claude", ["CLAUDE.md"]),
        ("skills", None),  # None = all .md files
        ("docs", None),
        ("config", None),
    ]

    count = 0
    for src_dir, file_list in source_dirs:
        base = Path(src_dir)
        if not base.exists():
            continue
        if file_list:
            files = [base / f for f in file_list if (base / f).exists()]
        else:
            files = list(base.rglob("*.md")) + list(base.rglob("*.yaml")) + list(base.rglob("*.json"))

        for fp in files:
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
                if len(content.strip()) < 20:
                    continue
                dest_name = str(fp).replace("\\", "_").replace("/", "_")
                dest = CFG.DOCS / dest_name
                dest.write_text(content, encoding="utf-8")
                count += 1
            except Exception as e:
                print(f"  SKIP {fp}: {e}")

    print(f"Copied {count} files to {CFG.DOCS}")

    # Now scan
    kb.watch()
    status = kb.stats()
    print(f"KB: {status['documents']} docs, {status['chunks']} chunks, engine={status['engine']}")
    print("Done.")

if __name__ == "__main__":
    main()
