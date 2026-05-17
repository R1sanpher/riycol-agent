---
title: "[DB] 表结构"
notion_id: "362a43b0-0cae-81f6-946d-df5f77578ebd"
last_synced: "2026-05-17T19:36:58"
notion_edited: "2026-05-16T20:56:00.000Z"
status: "synced"
---

conversations: id/session_id/role/content/source/token_count/created_at

-    索引: idx_conv_session(session_id) + idx_conv_created(created_at)

training_samples: id/instruction/output/source/dataset/quality/token_count/created_at

-    索引: idx_samples_dataset(dataset) + idx_samples_quality(quality)

knowledge_docs: id/doc_id(UNIQUE)/filename/chunk_count/indexed_at

agent_memory: agent_name/key/value(JSON)/updated_at/ttl(v2新增)

-    主键: (agent_name, key) | v2迁移: ALTER TABLE ADD COLUMN ttl REAL DEFAULT NULL

引擎: SQLite WAL + threading.Lock + PRAGMA busy_timeout=3000 + check_same_thread=False

API: DB.add_msg/sid/role/content/source/tokens | DB.add_sample(instruction/output/source/dataset/quality/tokens)

DB.get_samples(dataset,limit,min_score) | DB.stats() -> {messages,sessions,samples,docs}

批量: DB.begin_batch()/DB.end_batch() 引用计数 | 上下文: with DB: auto commit
