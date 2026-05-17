---
title: "[Skill] Agent Browser"
notion_id: "362a43b0-0cae-81e5-aaed-e0e00e1201af"
last_synced: "2026-05-17T19:36:59"
notion_edited: "2026-05-16T20:56:00.000Z"
status: "synced"
---

快速Rust无头浏览器自动化CLI, Node.js回退方案

安装: npm install -g agent-browser && agent-browser install

核心命令: open <url> | snapshot -i | click @e1 | fill @e2 'text' | screenshot out.png | extract

已知问题: Chrome二进制下载被GFW阻断 -> 使用 --executable-path 或 --auto-connect 连本地Chrome

项目集成: core/tools.py agent_browser工具 -> subprocess.run调用, 30s超时, 输出截断2000字符

状态: pending (need proxy for Chrome download)
