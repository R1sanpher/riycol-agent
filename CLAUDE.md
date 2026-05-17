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
- **思考先行**：动手前声明假设；需求模糊时列出 2-3 种解读让用户选择；不清楚时喊停。
- **极简实现**：不加没要求的功能，不为单次使用建抽象，200 行能变 50 行就重写。
- **精准改动**：只碰必须碰的代码，不顺手重构/改格式/升级风格。每个改动行都能追溯到需求。
- **目标驱动**：先定义可验证的成功标准（测试→实现→回归），循环直到通过。

## 2. 自动化执行标记
- 消息末尾加 `(auto)` → 可直接修改文件、执行测试命令，无需等确认。
- 输入 `手动模式` → 恢复所有写操作需确认。
- 破坏性命令（`rm -rf`、`git push --force`、`DROP TABLE` 等）必须确认，不受自动模式影响。

## 3. 架构速查

```
riycol-agent/           # 项目根
├── riycol.py           # CLI 入口 (argparse 子命令)
├── cli/riycol.py       # CLI 子命令实现
├── core/               # 核心模块 (config, db, logger, model_router, tools, retry, planner, reflection, memory_store, token_counter, prompt_manager, llm_bridge, vision, obsidian_writer, scheduler, plugin_loader, token_budget, model_manager)
├── plugins/            # server/, telegram/, agent/ (AgentSwarm+ReAct+CrewAI)
├── data/training/      # 微调管道
├── static/             # Web UI
├── tests/              # 137+ 单测
└── deploy/             # Docker
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
- `MemoryStore` 可通过 `MemoryStore(db=isolated_db)` 注入独立数据库用于测试。
- `MemoryStore` v2：`put()` 支持 `ttl` 参数（秒），`get()`/`list_keys()` 自动过期驱逐，`gc()` 手动清理。
- `MemoryStore.semantic_search(agent_name, query, top_k)` 需要注入 `vector_store`。

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
- **本地主力模型：qwen3:8b Q6_K（Ollama），GPU 当前 RTX 5060 Ti 16GB VRAM。**
- 本地后端：`LOCAL_MODEL_PROVIDER=ollama`。
- Ollama URL：`http://localhost:11434`。
- 云端兜底：DeepSeek API（`DEEPSEEK_API_KEY` + `DEEPSEEK_BASE_URL`）。
- 路由策略：`get_available_models()` 结果缓存 30s TTL，Ollama 优先。断路器开放时自动标记不可用。
- 断路器：`get_circuit_breaker(backend)`，`record_backend_success(backend)` / `record_backend_failure(backend)`。
- Agent/Crew 模型参数：`"deepseek"` / `"ollama"` / `"local"` / `"auto"` / `"mock"`。
- 更换模型流程：下载 GGUF → 写 Modelfile → `ollama create` → 改 `.env` → `LOCAL_MODEL` 属性同步。

### 4.6 Agent 层

**单一 Agent：** `plugins/agent/__init__.py` — `Agent` + `AgentSwarm` + `raw_llm_call()`
- 五个执行模式：`act()` 单轮 / `act_with_tools()` function calling / `act_with_react()` ReAct (Thought→TOOL_CALL/ARGUMENTS→Observation→FINAL_ANSWER) / `act_with_plan()` 规划执行 / `act_with_reflection()` 反思精炼
- `compact_memory()` LLM摘要旧消息保留最近4条，`MAX_MEMORY` 触发时自动调用

**AgentSwarm：** Core Riycol + 4 专用 Agent（reviewer, researcher, writer, coder），`run(task, parallel=True)` Planner分解+ThreadPoolExecutor(4)并行

**CrewAI：** `plugins/agent/crew_agent.py` — 5 角色，`decompose_task()` 自动分解+末尾加 reviewer，不依赖外部 crewai 包

**共享 LLM：** `raw_llm_call()` 模块级函数，带 `@retry(max_attempts=3)`

**工具定义：** `core/tools.py` — `Tool` 四要素 (name_for_human/name_for_model/description/parameters)，`Tool.to_dict()` 导出

### 4.7 Prompt 管理
- 全局单例：`from core.prompt_manager import prompts`。
- 模板格式：category/name 二级注册，`{{var}}` 占位符。
- 热加载：`prompts.load_file("data/prompts.json")`。
- 版本升级：`prompts.upgrade_template(cat, name, new_template, reason)` → 自动归档旧版。
- 批量导入：`python scripts/import_prompts.py`（从 Obsidian .md 文件导入）。
- 当前 38 模板：chat (7) + marketing (28) + vision (1) + summary (2)。

### 4.8 HTTP API
- 路由添加位置：`Handler.do_GET()` / `Handler.do_POST()` 的 `if/elif` 链
- 鉴权端点（`/metrics`, `/scheduler`, `/memory`, `/db/stats`, `/prompts`）须 `check_auth(handler)`
- `chat_lock`（公开）保护 `chat_history`，WS 和 HTTP 均须持有
- WebSocket 验证 `Origin` 头（`_is_origin_allowed`）
- 全部端点参考 `plugins/server/handler.py`

### 4.9 依赖与测试
- `pip install ".[all]"` 运行时 / `".[dev]"` 测试lint (pytest+ruff)
- 测试：`pytest tests/ -v` 全部 / `pytest tests/ -v --ignore=tests/test_e2e.py --ignore=tests/test_handler.py` 核心
- Lint：`python -m ruff check core/ plugins/ cli/ tests/ --ignore E501`
- 测试必须用 `tmp_path` fixture，禁止写项目文件

### 4.10 CI
- GitHub Actions：`.github/workflows/ci.yml`
- 矩阵：Windows + Ubuntu × Python 3.10 / 3.11 / 3.12
- 步骤：`pip install ".[dev]"` → `pytest tests/ -v --tb=short` → `python riycol.py validate` → `python riycol.py version`
- Lint 单独 job（Ubuntu, 3.12），`ruff check core/ plugins/ cli/ tests/ --ignore E501`

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
- 工作流钩子：`.claude/settings.local.json` — `PostToolUse(Agent)` → 流水线阶段提示
- 开发流水线子代理（定义于 `.claude/CLAUDE.md`）：pm-spec → architect → implementer → tester → reviewer
- MCP：notion (HTTP, https://mcp.notion.com/mcp)

## 8. Ollama 性能
- 模型：当前 qwen3:8b Q6_K (~6.7GB)，GPU RTX 5060 Ti 16GB VRAM，充裕。
- Modelfile：`config/qwen3.Modelfile`（`num_ctx 4096` + `num_predict 512`）。
- 环境变量：`config/ollama-env.ps1`（`FLASH_ATTENTION=1`, `KV_CACHE_TYPE=q8_0`, `NUM_PARALLEL=1`）。
- Ollama OpenAI 兼容端点不支持 `extra_body` 参数。

## 9. 禁止事项
- 不在 `core/config.py` 中硬编码路径/密钥。
- 不使用裸 `except:`。
- 不在 Agent 中 `from handler import llm`（循环依赖），改用 `model_router` 或延迟导入。
- 不在测试中写入项目真实文件。
- 不引入新的 `os.environ.get()` 到非 config.py 文件。
- 不搞 SQL 关键字黑名单（用 authorizer 白名单）。
- 不用 `str.startswith()` 做路径包含（用 `Path.relative_to()`）。
