---
title: "[Session] Config Refactor + Eval Baseline (2026-05-17)"
notion_id: "363a43b0-0cae-819e-bbe3-cd47d0e4d716"
last_synced: "2026-05-17T19:36:44"
notion_edited: "2026-05-17T10:23:00.000Z"
status: "synced"
---

[2026-05-17 18:23:15]
## 完成工作

### 1. Config 根治
- core/config.py 重写：分组管理，一次性加载环境变量
- 消除 plugins/server/kb.py 和 vector_kb.py 中的 4 处散落 os.environ.get()
- 同步 .env.example，202 测试全部通过

### 2. Eval 基线建立
- 5 套件 14 用例 baseline 完成
- 通过率: basic 66.7%, tool_use 0%, reasoning 100%, safety 40%, code 50%
- 结果保存至 data/eval/baseline.json

### 3. MCP 扩张（待继续）
- 已分析 plugin_loader.py、core/tools.py
- 已有 8 个内置工具

