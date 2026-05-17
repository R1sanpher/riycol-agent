---
title: "[Hook] Hooks 配置"
notion_id: "362a43b0-0cae-8189-857c-dba4602295c8"
last_synced: "2026-05-17T19:36:49"
notion_edited: "2026-05-16T20:56:00.000Z"
status: "synced"
---

.claude/settings.json:

- UserPromptSubmit: activator.ps1(自改进agent) + session-sync.ps1(跨会话状态注入)

- PostToolUse Bash: error-detector.ps1(命令错误检测)

- PostToolUse Agent: 开发流水线提示(pm-spec->architect->implementer->tester->reviewer)

- enabledMcpjsonServers: [notion]

.claude/settings.local.json:

- defaultMode: auto

- permissions.allow: 60+条目 (PowerShell cmdlets + python/git/ollama/docker + WebSearch/WebFetch/Skill/Agent)

- permissions.deny: 系统目录(C:\Windows/C:\Program Files) + reg + del /f + rm -rf

- acceptEdits: true

- hooks.PostToolUse Agent: 流水线阶段提示
