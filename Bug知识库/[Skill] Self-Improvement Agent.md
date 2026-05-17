---
title: "[Skill] Self-Improvement Agent"
notion_id: "362a43b0-0cae-8198-ae3f-ee7ff751b394"
last_synced: "2026-05-17T19:37:00"
notion_edited: "2026-05-16T20:56:00.000Z"
status: "synced"
---

触发条件: 命令失败/被纠正/发现新需求/API失败/知识过时/发现更优方案

流程: 捕获事件 -> 分类(correction|knowledge_gap|best_practice) -> 写入.learnings/

日志格式: [LRN-YYYYMMDD-XXX] + Priority(low|medium|high|critical) + Status(pending|resolved|promoted) + Area + Summary + Suggested Action

规则: 同类条目3次以上 -> 升级到CLAUDE.md永久规范

钩子: UserPromptSubmit(activator.ps1) + PostToolUse Bash(error-detector.ps1)

当前状态: errors:1(agent-browser下载被GFW阻断) | learnings:7(prompt升级记录) | features:1(TG浏览器agent)

目录: .learnings/ERRORS.md / LEARNINGS.md / FEATURE_REQUESTS.md / prompts_archive/
