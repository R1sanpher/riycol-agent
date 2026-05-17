# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 0. 路径与入口
- 项目根路径：`d:/riycol-agent/`
- 项目入口：`python riycol.py`（CLI 统一入口，argparse 子命令）
- 服务器入口：`python riycol.py run server`

## 1. 语言与代码风格
- 用中文回答，但代码注释、变量名、函数名一律英文。
- 修改文件前，必须先 Read 读取最新内容。
- 不写冗余注释，代码自解释。
- 不引入不必要的抽象，三个相似行好过一个过早的 helper。
- 禁止裸 `except:`（必须指定异常类型）。

## 2. 自动化执行标记
- 消息末尾加 `(auto)` → 可直接修改文件、执行测试命令，无需等确认。
- 输入 `手动模式` → 恢复所有写操作需确认。
- 破坏性命令（`rm -rf`、`git push --force`、`DROP TABLE` 等）必须确认，不受自动模式影响。

## 3. 架构速查

```
riycol-agent/
├── riycol.py                 # CLI 入口 (argparse)
├── cli/riycol.py             # CLI 子命令实现
├── core/
│   ├── config.py             # 单例配置 (CFG)，@property 读取 os.environ，_safe_int() 安全解析
│   ├── db.py                 # SQLite WAL + threading.Lock + begin_batch/end_batch + context manager
│   ├── logger.py             # stdlib logging + 轮转
│   ├── plugin_loader.py      # 插件自动发现与生命周期
│   ├── scheduler.py          # 轻量任务调度器 (interval + daily cron)
│   ├── memory_store.py       # Agent 持久化 key-value 记忆，构造函数可选 db= 注入测试隔离
│   ├── tools.py              # Tool-use function calling (9 builtins)，DB 查询用 set_authorizer 白名单
│   ├── token_counter.py      # Token 计数 (tiktoken > llama > char/4)
│   ├── token_budget.py       # Token 预算管理 + ChatML prompt 组装，历史选择 O(n)
│   ├── model_router.py       # 自动路由: Ollama(gemma4-e4b)优先，可用性缓存 30s TTL
│   ├── model_manager.py      # GGUF 模型下载/列表
│   ├── prompt_manager.py     # Prompt 模板引擎 ({{var}} 替换, 版本管理)
│   ├── llm_bridge.py         # 本地模型统一接口 (Ollama + llama-cpp)
│   ├── vision.py             # 图片分析 (DeepSeek API + 本地 llava)
│   └── obsidian_writer.py    # Obsidian vault 笔记写入，filename 自动消毒
├── plugins/
│   ├── server/               # HTTP API (handler + kb + vector_kb + ws_handler)
│   ├── telegram/             # Telegram bot (bot ThreadPoolExecutor + ai + stats)
│   └── agent/                # 单一 Riycol Agent + AgentSwarm + 自主任务
├── data/training/            # 微调管道 (prepare/clean/validate/convert/config)
├── static/index.html         # Web UI (SSE + WebSocket 双模式)
├── tests/                    # 98 单元测试 (db 29 + kb 24 + handler 10 + agent 20 + e2e 14)
└── deploy/                   # Docker + docker-compose
```

## 4. 关键约定

### 4.1 配置
- 所有配置通过 `from core.config import CFG` 单例读取。
- 新增配置项：在 Config 类添加 `@property`，用 `_safe_int()` 解析整数环境变量（自动处理 ValueError）。
- 禁止在其他文件中散落 `os.environ.get()`。

### 4.2 日志
- 使用 `from core.logger import log`。
- 级别：`log.debug()` / `log.info()` / `log.warn()` / `log.error()`。

### 4.3 数据库
- 使用 `from core.db import DB` 全局单例。
- 禁止字符串拼接 SQL —— 必须用 `?` 参数化。
- 批量写入使用 `DB.begin_batch()` / `DB.end_batch()` 减少 fsync。
- `DB` 支持 `with DB:` 上下文管理器。
- MemoryStore 可通过 `MemoryStore(db=isolated_db)` 注入独立数据库用于测试。

### 4.4 安全约束（必须遵守）

**路径安全：**
- 用户提供的文件名必须消毒：`Path(filename).name` 去除目录组件。
- 目录包含检查用 `path.resolve().relative_to(root.resolve())`，捕获 `ValueError`。
- 禁止用 `str.startswith()` 做路径包含判断（前缀可绕过）。

**SQL 安全：**
- 工具查询必须用 `sqlite3.set_authorizer()` 回调做白名单控制（仅允许 SELECT/READ/FUNCTION/RECURSIVE/PRAGMA）。
- 查询后 `finally` 块必须 `set_authorizer(None)` 恢复。
- 禁止 SQL 关键字黑名单。

**输出安全：**
- 异常消息不暴露内部路径、配置值、网络信息给终端用户。
- 前端 Markdown 渲染器已有 HTML 预转义（`&`/`<`/`>`），修改 `renderMD()` 时不能打破该保护链。

### 4.5 模型层
- **本地主力模型：gemma4-e4b（Ollama），锁定，不可删除/更换。**
- 本地后端：`LOCAL_MODEL_PROVIDER=ollama`（非 llama-cpp）。
- Ollama URL：`http://localhost:11434`。
- 云端兜底：DeepSeek API（`DEEPSEEK_API_KEY` + `DEEPSEEK_BASE_URL`）。
- 路由策略：`get_available_models()` 结果缓存 30 秒，简单短任务 → Ollama，技术/多轮/长文本 → DeepSeek。
- Agent 模型参数：`"deepseek"` / `"ollama"` / `"local"` / `"auto"` / `"mock"`。

### 4.6 Agent
- 单一 Agent 角色（Riycol），system_prompt 支持三种形式：
  - `("chat", "default")` — 从 PromptLibrary 渲染
  - `"原始字符串"` — 向后兼容
  - `None` → 默认 `("chat", "default")`
- Tool-use 自动使用 `chat/tool_use` 模板。
- 新增 Tool：在 `core/tools.py` 的 `_builtin_tools` 列表注册。

### 4.7 Prompt 管理
- 全局单例：`from core.prompt_manager import prompts`。
- 模板格式：category/name 二级注册，`{{var}}` 占位符。
- 热加载：`prompts.load_file("data/prompts.json")`。
- 版本升级：`prompts.upgrade_template(cat, name, new_template, reason)` → 自动归档旧版。

### 4.8 HTTP API
- GET 路由在 `Handler.do_GET()` 的 `if/elif` 链中添加。
- POST 路由在 `Handler.do_POST()` 的 `if/elif` 链中添加。
- 鉴权端点（`/metrics`, `/scheduler`, `/memory`, `/db/stats`, `/prompts`）须调用 `check_auth(handler)`。
- `chat_lock`（公开）保护 `chat_history` 的并发访问，WS 和 HTTP 处理器均须持有该锁。
- WebSocket 升级前验证 `Origin` 头（`_is_origin_allowed`）。

#### 可用端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（model/db/kb 状态） |
| GET | `/metrics` | 指标监控（鉴权） |
| GET | `/prompts` | 列出模板（鉴权） |
| POST | `/prompts/reload` | 热加载模板（鉴权） |
| POST | `/prompts/preview` | 渲染预览（鉴权） |
| POST | `/chat` | 非流式聊天 |
| POST | `/chat/stream` | SSE 流式聊天 |
| POST | `/clear` | 清除会话（新增 POST 路由） |
| GET | `/kb/status` | 知识库状态 |
| POST | `/kb/upload` | 上传文档 |
| POST | `/kb/add` | 添加文本 |
| POST | `/kb/delete` | 删除文档 |
| GET | `/ws` | WebSocket 升级 |

### 4.9 测试
- 测试文件命名：`tests/test_<模块>.py`。
- 运行全部：`pytest tests/ -v`
- 运行单文件：`pytest tests/test_db.py -v`
- 运行单测试：`pytest tests/test_agent.py::TestAgentSwarm::test_swarm_run -v`
- Lint：`ruff check .`
- Lint 修复：`ruff check --fix .`
- Pre-commit：`.pre-commit-config.yaml`（ruff check + format）
- 新增模块必须有对应测试文件。
- 测试必须使用 `tmp_path` fixture 隔离文件操作，禁止写入项目真实文件。

## 5. Token 优化
- 使用 `core/token_budget.py` 的 `TokenBudget` 控制输入量。
- KB 上下文预算：300 tokens。
- 聊天历史裁剪：`_trim(max_msgs=10)` — 5 轮。
- 使用 `core/token_counter.py` 的 `count()` 计数，不用 `len(x)//4`。

## 6. Self-Improvement 学习循环
当遇到错误、被纠正、发现更优方案时，记录到 `.learnings/`：
- 命令失败 → `.learnings/ERRORS.md`
- 被纠正/新发现 → `.learnings/LEARNINGS.md`（category: correction | knowledge_gap | best_practice）
- 用户想要功能 → `.learnings/FEATURE_REQUESTS.md`

日志格式：
```markdown
## [LRN-YYYYMMDD-XXX] best_practice
**Priority**: low|medium|high|critical
**Status**: pending|resolved|promoted
**Area**: frontend|backend|infra|tests|docs|config
### Summary
一句话
### Suggested Action
具体改进建议
```

同类条目出现 3 次以上 → 升级到 CLAUDE.md 作为永久规范。

## 7. Skills, Hooks & MCP
- Skills：`skills/self-improving-agent/` + `skills/agent-browser/`
- Hooks：`.claude/settings.json` — `UserPromptSubmit` → `activator.ps1`，`PostToolUse(Bash)` → `error-detector.ps1`
- MCP：notion (HTTP, https://mcp.notion.com/mcp)

## 8. Ollama 性能
- 模型：gemma4-e4b，RTX 5060 Ti 4GB VRAM 有溢出。
- Modelfile：`config/gemma4-opt.Modelfile`（`num_ctx 2048` + `num_predict 512`）。
- 环境变量：`config/ollama-env.ps1`（`FLASH_ATTENTION=1`, `KV_CACHE_TYPE=q8_0`, `NUM_PARALLEL=1`）。
- 单条回复约 50s（瓶颈在显存溢出）。
- Ollama OpenAI 兼容端点不支持 `extra_body` 参数。

## 9. 禁止事项
- 不在 `core/config.py` 中硬编码路径/密钥。
- 不使用裸 `except:`。
- 不在 Agent 中 `from handler import llm`（循环依赖），改用 `model_router` 或延迟导入。
- 不在测试中写入项目真实文件。
- 不修改 `LOCAL_MODEL`（gemma4-e4b 已锁定）。
- 不引入新的 `os.environ.get()` 到非 config.py 文件。
- 不搞 SQL 关键字黑名单（用 authorizer 白名单）。
- 不用 `str.startswith()` 做路径包含（用 `Path.relative_to()`）。
