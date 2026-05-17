---
title: "untitled-362a43b0"
notion_id: "362a43b0-0cae-8137-9483-f3e569b68933"
last_synced: "2026-05-17T04:59:15"
notion_edited: "2026-05-16T20:56:00.000Z"
status: "synced"
---

riycol-agent v2.2.0 — 多Agent AI服务平台

三层架构:

- 入口层: riycol.py -> cli/riycol.py (15个子命令)

- 核心层: 23个模块 (config/db/retry/planner/reflection/memory/tools/prompt/sync等)

- 插件层: server (HTTP API 20+端点) / telegram (Bot) / agent (5模式Multi-Agent)

技术栈:

- Python 3.10+ | Ollama (qwen3:8b Q6_K, 6.7GB) | DeepSeek API

- SQLite WAL + threading.Lock | ChromaDB (SentenceTransformer)

- HTTP: stdlib HTTPServer + SSE + WebSocket | 前端: 原生 HTML/CSS/JS

- pytest 179用例 | ruff lint | GitHub Actions CI (Win+Ubuntu, Py3.10-3.12)

数据流: 用户输入 -> model_router.route() -> Agent.act/act_with_react/act_with_plan -> raw_llm_call() -> [DeepSeek|Ollama|llama-cpp] -> Tool.execute()(可选) -> memory_store + DB 持久化

当前状态: 179核心测试通过 | 1,392,862训练样本 | 80条对话 | 3个会话 | 40个Prompt模板
