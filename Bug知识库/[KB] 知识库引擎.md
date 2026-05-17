---
title: "[KB] 知识库引擎"
notion_id: "362a43b0-0cae-81f0-bde8-e3d665894244"
last_synced: "2026-05-17T19:36:54"
notion_edited: "2026-05-16T20:56:00.000Z"
status: "synced"
---

KnowledgeBase (plugins/server/kb.py):

- 模式: keyword(TF-IDF CJK字符级分词) / vector(ChromaDB) / hybrid(混合,默认)

- 支持的格式: .txt/.md/.json/.yaml/.yml/.pdf(PyPDF2+pdfplumber)/.docx(python-docx)/.py

- query(question, top_k=5) -> {has_result, sources, engine, token_cost, context}

- add_text(text, filename) — 追加文本并重扫描

- watch(interval=30) — 增量扫描(mtime), 后台线程

- stats() -> {enabled, engine, documents, mode}

VectorKnowledgeBase (plugins/server/vector_kb.py):

- ChromaDB PersistentClient, collection: riycol_kb, HNSW cosine空间

- add_document(filepath) — 段落+句子分块, doc_id去重

- query(question, top_k=5) — 语义搜索

- delete_document(filename) — 删除所有匹配chunks

- Embedding: all-MiniLM-L6-v2(384d)/bge-small-zh-v1.5(512d)/bge-base-en-v1.5(768d)/paraphrase-multilingual(384d)
