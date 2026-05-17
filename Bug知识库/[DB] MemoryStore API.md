---
title: "[DB] MemoryStore API"
notion_id: "362a43b0-0cae-81ce-b3d7-ef3661561769"
last_synced: "2026-05-17T19:36:56"
notion_edited: "2026-05-16T20:56:00.000Z"
status: "synced"
---

位置: core/memory_store.py, MemoryStore类, 全局单例 memory_store

构造: MemoryStore(db=None, vector_store=None) — db注入测试隔离, vector_store注入语义搜索

核心方法:

- put(agent_name, key, value, ttl=None) — 存储JSON, TTL秒

- get(agent_name, key, default=None) — 读取, 自动过期驱逐

- list_keys(agent_name) -> list[str] — 按updated_at DESC排序

- delete/clear_agent — 删除

- gc() -> int — 清理过期条目, 返回删除数量

- stats() -> {total_entries, agents: {name: count}}

- semantic_search(agent_name, query, top_k=5) -> list[dict] — 需注入vector_store
