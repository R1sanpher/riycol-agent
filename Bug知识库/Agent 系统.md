---
title: "Agent 系统"
notion_id: "362a43b0-0cae-8184-8d82-f3bf0753a378"
last_synced: "2026-05-17T18:26:20"
notion_edited: "2026-05-16T20:56:00.000Z"
status: "synced"
---

# Agent 系统

详细文档请查看：[[00-Project/Core/Agent系统指南]]

### 快速参考

5 个执行模式：
1. `act()` — 单轮直接回答
2. `act_with_tools()` — Function calling [DeepSeek]
3. `act_with_react()` — ReAct 范式
4. `act_with_plan()` — 规划执行
5. `act_with_reflection()` — 反思精炼

AgentSwarm：Core Riycol + 4 专用 Agent（reviewer/researcher/writer/coder）

8 个内置工具：read_file / write_file / search_kb / db_query / get_time / web_fetch / agent_browser / describe_image
