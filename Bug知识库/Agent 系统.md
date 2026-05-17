---
title: "Agent 系统"
notion_id: "362a43b0-0cae-8184-8d82-f3bf0753a378"
last_synced: "2026-05-17T18:26:20"
notion_edited: "2026-05-16T20:56:00.000Z"
status: "synced"
---

5个执行模式:

1. act(task, context) — 单轮直接回答 [所有后端]

2. act_with_tools(task, max_rounds=3) — OpenAI function calling [DeepSeek专用]

3. act_with_react(task, max_rounds=5) — ReAct范式: Thought->TOOL_CALL/ARGUMENTS->Observation->FINAL_ANSWER [所有后端]

4. act_with_plan(task, reflect=False) — Plan->Execute->Synthesize->(opt)Reflect [所有后端] [新]

5. act_with_reflection(task, max_refine_rounds=2) — Act->Critique->Refine闭环 [所有后端] [新]

AgentSwarm 多智能体:

- Core Riycol + 4专用Agent: reviewer/researcher/writer/coder

- run(task, parallel=True) — Planner分解 -> ThreadPoolExecutor(4)并行 -> _synthesize综合

- run(task, parallel=False) — 顺序执行，前序结果传递

- 3个自主任务: 每日摘要(08:00) / KB巡检(每小时) / 记忆清理(03:00)

8个内置工具: read_file / write_file / search_kb / db_query(只读authorizer白名单) / get_time / web_fetch / agent_browser / describe_image

共享LLM调用: raw_llm_call(model, system, user, history, temperature, max_tokens) — 模块级函数，@retry(max_attempts=3)

compact_memory() — LLM摘要替代硬截断，保留最近4条 | _error标记自动过滤 | last_reply_was_error检查
