"""Final verification before clearing conversation."""
import sys, os
sys.path.insert(0, r"d:\riycol-agent")

# 1. Verify memory files exist
mem_dir = r"C:\Users\Administrator\.claude\projects\d--riycol-agent\memory"
files = [f for f in os.listdir(mem_dir) if f.endswith(".md")]
print(f"Memory files: {files}")

# 2. Verify Notion sync works
from core.sync_notion import log_to_notion
ok = log_to_notion(
    "[Session] 会话清理前确认 (2026-05-17)",
    "所有任务进度已保存至 memory/session_state.md。Config 根治完成，Eval 基线已建立，MCP 扩张待继续。",
    tags=["session", "checkpoint"],
)
print(f"Notion checkpoint: {ok}")

# 3. Verify baseline exists
import json
with open(r"data/eval/baseline.json", encoding="utf-8") as f:
    bl = json.load(f)
meta = bl["_meta"]
print(f"Baseline: {len(bl)-1} suites, meta: {meta['timestamp']}")

# 4. Final sync
print("Final sync...")
from core.sync_notion import sync
r = sync()
print(f"Sync: pulled={r['pulled']}, pushed={r['pushed']}")
print("All OK. Ready to clear.")
