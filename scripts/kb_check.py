import sys; sys.path.insert(0, ".")
from core.config import CFG
from plugins.server.kb import KnowledgeBase

kb = KnowledgeBase(docs_dir=str(CFG.DOCS), mode="keyword")
kb.watch()
s = kb.stats()
print(f"engine={s['engine']} documents={s['documents']}")
