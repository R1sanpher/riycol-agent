# riycol-agent 操作指南

## 1. 权限配置 (settings.local.json)

### 作用
让 Claude Code 自动执行常见操作，减少手动确认次数。**破坏性命令仍需确认**，安全不受影响。

### 文件位置
```
d:\riycol-agent\settings.local.json   （项目根目录）
```

### 配置项说明

```json
{
  "permissions": {
    "allow": [
      // === 文件操作 ===
      "Read",             // 读取文件
      "Write",            // 写入新文件
      "Edit",             // 编辑现有文件
      "MultiEdit",        // 批量编辑

      // === 命令 (Bash = PowerShell on Windows) ===
      "Bash(python:*)",   // 所有 Python 命令 (运行项目、测试)
      "Bash(pytest:*)",   // 运行测试
      "Bash(ruff:*)",     // Lint 检查
      "Bash(pip:*)",      // 安装依赖
      "Bash(git:status)", // Git 状态
      "Bash(git:diff)",   // Git 差异
      "Bash(git:add)",    // Git 暂存
      "Bash(git:commit)", // Git 提交
      "Bash(ollama:*)",   // Ollama 模型管理
      "Bash(npm:*)",      // Node.js 操作
      "Bash(code:*)",     // VS Code CLI

      // === 网络 ===
      "WebSearch",        // 网页搜索
      "WebFetch"          // 网页内容抓取
    ],
    "deny": []            // 黑名单 (留空)
  },
  "acceptEdits": true     // 自动接受文件修改
}
```

### 注意事项
- **始终需要确认的破坏性操作**：`rm -rf`、`git push --force`、`DROP TABLE`、删除文件
- `Bash(command:*)` 中的 `*` 是通配符，匹配所有子命令
- `deny` 优先级高于 `allow`

---

## 2. 本项目完整配置

### 环境变量 (.env)
```bash
# 本地模型 (Ollama)
LOCAL_MODEL_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# 云端模型
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 代理 (翻墙)
TG_PROXY=http://127.0.0.1:7897    # Clash Verge 默认混合端口
NOTION_PROXY=                     # 默认回退到 TG_PROXY

# 服务端口
PORT=8000
```

### Hooks 钩子 (.claude/settings.json)
| 钩子 | 触发时机 | 脚本 |
|------|---------|------|
| UserPromptSubmit | 每次用户输入 | `activator.ps1` + `session-sync.ps1` |
| PostToolUse(Bash) | 每次命令执行后 | `error-detector.ps1` |

### Skills 技能
| 技能 | 触发命令 |
|------|---------|
| update-config | `/config` 或修改配置文件 |
| loop | `/loop <间隔> <命令>` |
| claude-api | 涉及 Anthropic SDK 的代码 |
| init | `/init` 初始化/更新 CLAUDE.md |
| review | `/review` 代码审查 |
| security-review | `/security-review` 安全审查 |

---

## 3. 常用命令速查

### 开发
```bash
# 安装依赖
pip install ".[dev]"

# 运行全部测试
pytest tests/ -v

# 运行核心测试 (跳过 e2e/handler)
pytest tests/ -v --ignore=tests/test_e2e.py --ignore=tests/test_handler.py

# 运行单文件测试
pytest tests/test_agent.py -v

# 运行单测试
pytest tests/test_agent.py::TestAgentSwarm::test_swarm_run -v

# Lint
python -m ruff check core/ plugins/ cli/ tests/ --ignore E501

# Lint 修复
python -m ruff check core/ plugins/ cli/ tests/ --ignore E501 --fix
```

### 服务
```bash
python riycol.py run server       # HTTP API
python riycol.py run telegram     # Telegram Bot
python riycol.py run all          # 全部服务
```

### Agent
```bash
python riycol.py agent run "任务"              # 单 Agent
python riycol.py agent run "任务" --parallel   # 多 Agent 并行
python riycol.py agent run "任务" --reflect    # 带反思精炼
python riycol.py crew run "任务" --roles riycol reviewer  # 多角色协作
```

### 同步
```bash
python riycol.py sync notion --direction bidirectional  # Notion ↔ 本地
python riycol.py sync status                             # 同步状态
python riycol.py sync session --task "正在做XX"          # 注册跨会话任务
```

### 运维
```bash
python riycol.py validate       # 配置检查
python riycol.py model list     # 模型列表
python riycol.py db             # 数据库统计
python riycol.py memory         # 记忆存储统计
python riycol.py scheduler      # 调度器状态
```

---

## 4. 自动化标记

在消息末尾添加标记控制 Claude 行为：

| 标记 | 效果 |
|------|------|
| `(auto)` | 可直接修改文件、执行命令，无需确认 |
| `手动模式` | 恢复所有写操作需确认 |

---

## 5. Notion ↔ 本地同步设置

1. 确保 Clash Verge 代理运行中 (`127.0.0.1:7897`)
2. 运行 `python riycol.py sync notion --direction bidirectional`
3. 也可用 `--direction pull` (仅拉取) 或 `--direction push` (仅推送)

---

## 6. 目录结构速查

```
riycol-agent/
├── .claude/settings.json    # Hooks + MCP 配置
├── settings.local.json      # 权限白名单 (本地，不提交 Git)
├── .env                     # 环境变量 (密钥，不提交 Git)
├── riycol.py                # 入口
├── cli/riycol.py            # 所有子命令
├── core/                    # 核心模块 (config, db, agent, sync...)
├── plugins/                 # 插件 (server, telegram, agent)
├── tests/                   # 137+ 单测
├── docs/                    # 文档
└── Bug知识库/               # 本地知识库 (Notion 同步目标)
```
