# Errors

Command failures and integration errors.

---


## [ERR-20260515-001] agent-browser install

**Logged**: 2026-05-15T23:50:44
**Priority**: medium
**Status**: pending
**Area**: infra

### Summary
agent-browser Chrome 二进制下载被墙，无法从 storage.googleapis.com 下载

### Error
[network] Failed to download Chrome 148.0.7778.167 for win64 from Google storage

### Context
- 命令: agent-browser install
- 网络环境: 中国大陆，Google 服务不可达
- 替代方案: 可使用 --auto-connect 连本地已安装的 Chrome

### Suggested Fix
- 使用本地 Chrome: agent-browser --executable-path <path> 或 --auto-connect
- 或手动下载 Chrome 放到 agent-browser 目录

### Metadata
- Reproducible: yes
- Related Files: N/A

---
