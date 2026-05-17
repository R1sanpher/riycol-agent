"""Self-validation: KB + DB + Skills + Memory"""
import sys; sys.path.insert(0, ".")

print("=" * 50)
print("RIYCOL AGENT — SELF-VALIDATION")
print("=" * 50)

# 1. Knowledge Base
from core.config import CFG
from plugins.server.kb import KnowledgeBase
kb = KnowledgeBase(docs_dir=str(CFG.DOCS), mode="keyword")
kb.watch()
s = kb.stats()
print(f"\n[KB]  engine={s['engine']}  documents={s['documents']}")

# 2. Database
from core.db import DB
db_stats = DB.stats()
print(f"[DB]  messages={db_stats['messages']}  sessions={db_stats['sessions']}  "
      f"samples={db_stats['samples']}  knowledge_docs={db_stats['docs']}")

# 3. Skills
from core.skill_db import skill_registry
skill_registry.discover()
sk_stats = skill_registry.stats()
print(f"[SKILLS]  total={sk_stats['total_skills']}  categories={sk_stats['categories']}")

# 4. Memory
from core.memory_store import memory_store
mem_stats = memory_store.stats()
print(f"[MEMORY]  entries={mem_stats['total_entries']}  agents={len(mem_stats['agents'])}")

# 5. Prompts
from core.prompt_manager import prompts
print(f"[PROMPTS]  templates={prompts.template_count}")

# 6. Model
from core.model_router import get_available_models
models = get_available_models(force=True)
print(f"[MODEL]  ollama={models.get('ollama')}  local={models.get('local')}  deepseek={models.get('deepseek')}")

print("\n" + "=" * 50)
print("ALL SYSTEMS VALIDATED")
print("=" * 50)
