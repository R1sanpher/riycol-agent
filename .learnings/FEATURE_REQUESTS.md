# Feature Requests

Capabilities requested by the user.

---


## [FEAT-20260515-001] tg_browser_agent

**Logged**: 2026-05-15T23:51:17
**Priority**: medium
**Status**: pending
**Area**: backend

### Requested Capability
用户希望 Telegram Agent 能调用浏览器执行网页操作（搜索、截图、表单填写等）

### User Context
用户通过 TG 与 Agent 对话，希望 Agent 具备浏览器自动化能力来完成在线任务

### Complexity Estimate
medium

### Suggested Implementation
集成 agent-browser CLI：TG bot 收到消息后调用 agent-browser 执行网页操作，返回结果截图或文本

### Metadata
- Frequency: first_time
- Related Features: agent-browser skill

---
