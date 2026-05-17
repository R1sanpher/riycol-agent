# riycol-agent 全项目操作参考手册

> v2.2.0 | 最后更新 2026-05-17

---

## 目录
1. [项目概览](#1-项目概览)
2. [CLI 命令大全](#2-cli-命令大全)
3. [Agent 系统](#3-agent-系统)
4. [模型与路由](#4-模型与路由)
5. [知识库 (KB)](#5-知识库-kb)
6. [数据库](#6-数据库)
7. [记忆与同步](#7-记忆与同步)
8. [HTTP API](#8-http-api)
9. [Telegram Bot](#9-telegram-bot)
10. [微调管道](#10-微调管道)
11. [权限与安全](#11-权限与安全)
12. [故障排查](#12-故障排查)

---

## 1. 项目概览

```
riycol-agent/           # 多Agent AI 服务平台
├── riycol.py           # 入口 python riycol.py
├── cli/riycol.py       # 15 个子命令
├── core/               # 20 个核心模块
├── plugins/            # 3 个插件 (server, telegram, agent)
├── tests/              # 148+ 单元测试
├── data/               # 数据库、训练数据、ChromaDB
├── Bug知识库/          # 本地知识库 (.md)
├── docs/               # 文档
└── deploy/             # Docker
```

### 技术栈
| 层 | 技术 |
|----|------|
| LLM 后端 | Ollama (qwen3:8b) / DeepSeek API / llama-cpp GGUF |
| 数据库 | SQLite WAL + threading.Lock |
| 向量存储 | ChromaDB (SentenceTransformer embeddings) |
| HTTP 服务 | stdlib HTTPServer + SSE / WebSocket |
| 前端 | 原生 HTML/CSS/JS (SSE + WS 双模式) |
| 测试 | pytest (148+ 用例) |
| Lint | ruff (E501 ignored) |

---

## 2. CLI 命令大全

### `run` — 启动服务
```bash
python riycol.py run [all|server|telegram|agent]
```
- `all` — 全部插件
- `server` — HTTP API (端口 8000)
- `telegram` — Telegram Bot
- `agent` — Agent Swarm 后台运行

### `agent` — Agent 操作
```bash
python riycol.py agent list                    # 列出 Agent
python riycol.py agent run "<task>"            # 单 Agent 执行
python riycol.py agent run "<task>" --parallel # 多 Agent 并行
python riycol.py agent run "<task>" --reflect  # 带反思精炼
python riycol.py agent review "<task>"         # 带记忆上下文
```

### `crew` — 多角色协作
```bash
python riycol.py crew roles                                    # 列出角色
python riycol.py crew run "<task>"                             # 自动分配角色
python riycol.py crew run "<task>" --roles riycol researcher   # 指定角色
```

### `sync` — 同步
```bash
python riycol.py sync all                                      # 全同步
python riycol.py sync notion --direction [pull|push|bidirectional]
python riycol.py sync session --task "正在做XX"                # 注册跨会话任务
python riycol.py sync status                                   # 同步状态
```

### `model` — 模型管理
```bash
python riycol.py model list              # 列出可用模型
python riycol.py model check             # 检查模型可用性
python riycol.py model download <key>    # 下载 GGUF 模型
```

### `data` — 数据管理
```bash
python riycol.py data stats              # 数据统计
python riycol.py data build --limit N    # 构建训练数据
python riycol.py data export             # 导出训练数据
```

### `finetune` — 微调管道
```bash
python riycol.py finetune stats          # 管道状态
python riycol.py finetune prepare        # 数据准备
python riycol.py finetune clean          # 数据清洗
python riycol.py finetune validate       # 数据校验
python riycol.py finetune convert        # 格式转换
python riycol.py finetune config         # 生成训练配置
python riycol.py finetune all --limit N  # 全流程
```

### 其他
```bash
python riycol.py validate     # 配置检查
python riycol.py version      # 版本号
python riycol.py db           # 数据库统计
python riycol.py memory       # 记忆存储统计
python riycol.py scheduler    # 调度器状态
python riycol.py plugin list  # 插件列表
python riycol.py kb refresh   # 刷新知识库
python riycol.py kb stats     # 知识库统计
```

---

## 3. Agent 系统

### 五个执行模式

| 方法 | 流程 | 适用场景 |
|------|------|---------|
| `act(task)` | 单轮直接回答 | 简单问答 |
| `act_with_tools(task)` | OpenAI function calling | DeepSeek + 工具 |
| `act_with_react(task)` | Thought → TOOL_CALL → Observation → FINAL_ANSWER | 所有后端 + 工具 |
| `act_with_plan(task)` | Plan → Execute → Synthesize | 复杂多步任务 |
| `act_with_reflection(task)` | Act → Critique → Refine | 需要自审的任务 |

### 程序化调用
```python
from plugins.agent import Agent, AgentSwarm

# 单 Agent
agent = Agent("助手", "通用助手", system_prompt=("chat", "default"))
reply = agent.act("分析这个代码")
reply = agent.act_with_react("读取.env并解释配置")
reply = agent.act_with_plan("重构数据库模块", reflect=True)

# 多 Agent
swarm = AgentSwarm()
result = swarm.run("写 Python 异步框架对比报告", parallel=True)
```

### 8 个内置工具

| 工具 | 函数 | 用途 |
|------|------|------|
| read_file | `tool_read_file` | 读取项目文件 |
| write_file | `tool_write_file` | 写入项目文件 |
| search_kb | `tool_search_kb` | 搜索知识库 |
| db_query | `tool_db_query` | SQL 查询（只读） |
| get_time | `tool_get_time` | 服务器时间 |
| web_fetch | `tool_web_fetch` | 抓取网页 |
| agent_browser | `tool_agent_browser` | 浏览器自动化 |
| describe_image | `tool_describe_image` | 图片分析 |

### 自主任务（调度器注册）
- **每日摘要** (08:00)：总结昨日对话
- **KB 巡检** (每小时)：检查知识库健康
- **记忆清理** (03:00)：清理过期记忆

---

## 4. 模型与路由

### 三个后端

| 后端 | 配置 | 特点 |
|------|------|------|
| Ollama | `OLLAMA_URL=http://localhost:11434`, `OLLAMA_MODEL=qwen3:8b` | 本地主力 |
| DeepSeek | `DEEPSEEK_API_KEY=sk-xxx` | 云端兜底 |
| llama-cpp | `LOCAL_MODEL_PROVIDER=llama-cpp`, `MODEL_PATH=models/xxx.gguf` | 本地 GGUF |

### 路由策略
1. 缓存 30s TTL 检查可用性
2. Ollama 优先 → DeepSeek 长/技术任务 → 本地 GGUF 简单任务
3. 断路器开放时自动标记不可用，进入回退链

### 更换模型
```bash
# 1. 下载 GGUF
python riycol.py model download qwen3-8b

# 2. 创建 Ollama 模型
ollama create qwen3:8b -f config/qwen3.Modelfile

# 3. 修改 .env
OLLAMA_MODEL=qwen3:8b
```

### 断路器 API
```python
from core.model_router import get_circuit_breaker, record_backend_success, record_backend_failure

cb = get_circuit_breaker("deepseek")
print(cb.state)  # "closed" | "open" | "half_open"
record_backend_failure("deepseek")  # 记录失败
```

---

## 5. 知识库 (KB)

### 三种模式
| 模式 | 配置 | 适用 |
|------|------|------|
| keyword | `KB_MODE=keyword` | 轻量，CJK 分词 |
| vector | `KB_MODE=vector` | ChromaDB 语义搜索 |
| hybrid | `KB_MODE=hybrid` (默认) | 关键词+向量混合 |

### Embedding 模型
```bash
EMBEDDING_MODEL=all-MiniLM-L6-v2          # 英文轻量 (384d)
EMBEDDING_MODEL=bge-small-zh-v1.5         # 中文优化 (512d)
EMBEDDING_MODEL=paraphrase-multilingual   # 多语言 (384d)
```

### CLI 操作
```bash
python riycol.py kb refresh    # 重新扫描文档目录
python riycol.py kb stats      # 知识库统计
```

### 程序化操作
```python
from plugins.server.kb import KnowledgeBase

kb = KnowledgeBase(docs_dir="data/docs", mode="hybrid")
kb.watch()                      # 增量扫描新文档
result = kb.query("搜索词", top_k=5)  # {has_result, sources, context}
stats = kb.stats()              # {documents, chunks, engine}
```

### HTTP API
```
POST /kb/upload   — 上传文档 (multipart)
POST /kb/add      — 添加文本 {"text": "...", "source": "..."}
GET  /kb/status   — 知识库状态
POST /kb/delete   — 删除文档 {"doc_id": "..."}
```

---

## 6. 数据库

### 三张表

| 表 | 用途 | 关键字段 |
|----|------|---------|
| `conversations` | 对话记录 | session_id, role, content, token_count |
| `training_samples` | 训练数据 | instruction, output, dataset, quality |
| `agent_memory` | Agent 记忆 | agent_name, key, value, updated_at, ttl |

### DB API
```python
from core.db import DB

DB.add_msg(session_id, role, content, source="", tokens=0)
DB.add_sample(instruction, output, dataset="default", quality=1.0, source="")
DB.get_samples(dataset, limit=100, min_score=-1.0)
stats = DB.stats()  # {messages, sessions, samples}

# 批量写入
DB.begin_batch()
for item in items:
    DB.add_msg(...)
DB.end_batch()

# 上下文管理器
with DB:
    DB.add_msg(...)
```

### MemoryStore API
```python
from core.memory_store import memory_store

memory_store.put("agent_name", "key", value, ttl=3600)  # TTL 秒
value = memory_store.get("agent_name", "key", default=None)
keys = memory_store.list_keys("agent_name")
memory_store.delete("agent_name", "key")
memory_store.clear_agent("agent_name")
stats = memory_store.stats()
removed = memory_store.gc()  # 清理过期

# 语义搜索 (需注入 vector_store)
results = memory_store.semantic_search("agent_name", "query", top_k=5)
```

---

## 7. 记忆与同步

### 三条记忆通道

| 通道 | 存储 | 用途 |
|------|------|------|
| Agent Memory | `agent_memory` 表 (SQLite) | 对话历史、上下文 |
| Vector Memory | `data/chroma_memory/` (ChromaDB) | 语义搜索 |
| Session State | `_system` key (跨会话) | 多会话任务共享 |

### Notion ↔ 本地同步
```bash
# 确保 Clash Verge 运行中
python riycol.py sync notion --direction pull        # 拉取
python riycol.py sync notion --direction push        # 推送
python riycol.py sync notion --direction bidirectional  # 双向
```

### 跨会话状态
```python
from core.sync_session import sync_task, get_active_tasks, update_context

tid = sync_task("正在修复Bug #42", "in_progress")
tasks = get_active_tasks()
update_context("handoff_note", "请继续完成 #42 的修复")
```

每次输入时钩子自动显示: `[SYNC] N active tasks across sessions`

---

## 8. HTTP API

### 端点速查
```
GET  /health              # 健康检查 (公开)
GET  /ping                # 轻量探活 (公开)
GET  /metrics             # 指标监控 (鉴权)
GET  /db/stats            # 数据库统计 (鉴权)
GET  /scheduler           # 调度器状态 (鉴权)
GET  /memory              # Agent 记忆 (鉴权)
GET  /prompts             # 模板列表 (鉴权)
POST /prompts/reload      # 热加载模板 (鉴权)
POST /prompts/preview     # 渲染预览 (鉴权)
POST /chat                # 非流式聊天
POST /chat/stream         # SSE 流式聊天
POST /clear               # 清除会话
GET  /kb/status           # 知识库状态
POST /kb/upload           # 上传文档
POST /kb/add              # 添加文本
POST /kb/delete           # 删除文档
GET  /ws                  # WebSocket 升级
```

### 鉴权
```bash
curl -H "Authorization: Bearer my-secret-key" http://localhost:8000/metrics
```

### SSE 流式示例
```javascript
const sse = new EventSource('/chat/stream');
// or fetch:
const resp = await fetch('/chat/stream', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({message: 'hello', session_id: 'abc'})
});
// read resp.body as SSE stream
```

### 限流配置
- 滑动窗口: 60 req/min per IP
- 推理并发: max 2 (ChatQueue Semaphore)
- 会话上限: MAX_CHAT_SESSIONS=500 (LRU 驱逐)

---

## 9. Telegram Bot

### 配置
```bash
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_ALLOWED_USERS=123456,789012    # 留空=不限制
TG_MODEL=auto                           # auto|deepseek|ollama|local
```

### 架构
- ThreadPoolExecutor (max 10) 并发处理
- 消息 >4096 字符自动分段
- 指数退避重试 (3 次)
- typing indicator 模拟延迟 (DELAY_MIN/MAX)
- 代理支持: TG_PROXY
- 敏感词过滤: BLACKLIST_KEYWORDS

### 后端选择
| TG_MODEL | 含义 |
|----------|------|
| auto | 自动路由 (Ollama 优先) |
| deepseek | DeepSeek API |
| ollama | Ollama 本地 |

---

## 10. 微调管道

### 流程
```
prepare → clean → validate → convert → config → train
```

### 数据格式
- **Alpaca**: `{"instruction": "...", "output": "..."}`
- **ShareGPT**: `{"conversations": [{"from": "human", "value": "..."}, {"from": "gpt", "value": "..."}]}`

### 支持模型
- Qwen2.5 系列 (1.5B, 7B, 14B)
- LoRA / QLoRA (Unsloth)
- 本地 GGUF 推理

### 数据统计
当前训练数据: 1,392,862 条样本
- 来源: Chinese-Vicuna, firefly-1.1M 等

---

## 11. 权限与安全

### settings.local.json (建议配置)
```json
{
  "permissions": {
    "allow": ["Read","Write","Edit","Bash(python:*)","Bash(pytest:*)",
              "Bash(git:status)","Bash(git:diff)","Bash(git:add)",
              "Bash(git:commit)","Bash(code:*)"],
    "deny": []
  },
  "acceptEdits": true
}
```

### 安全底线 (始终确认)
- `rm -rf`、文件删除
- `git push --force`
- `DROP TABLE`、`DELETE FROM`
- 所有 `deny` 列表中的操作

### 代码安全规范
- SQL 必须 `?` 参数化，禁止字符串拼接
- 文件路径必须 `Path().relative_to()` 验证
- 工具 DB 查询必须 `set_authorizer()` 白名单
- 异常消息不暴露路径/密钥

---

## 12. 故障排查

### Ollama 不响应
```bash
# 检查 Ollama 进程
ollama list
curl http://localhost:11434/api/tags

# 加载环境变量
. config/ollama-env.ps1
```

### 模型性能优化
```bash
# config/ollama-env.ps1
$env:FLASH_ATTENTION = "1"
$env:KV_CACHE_TYPE = "q8_0"
$env:NUM_PARALLEL = "1"
```

### Notion 同步失败
```bash
# 1. 确认代理运行
curl -x http://127.0.0.1:7897 https://api.notion.com/v1/users/me -H "Authorization: Bearer ntn_xxx" -H "Notion-Version: 2022-06-28"

# 2. 检查 .env
TG_PROXY=http://127.0.0.1:7897
```

### 测试失败
```bash
# 运行核心(跳过长耗时)
pytest tests/ -v --ignore=tests/test_e2e.py --ignore=tests/test_handler.py

# 查看详细输出
pytest tests/test_agent.py -v --tb=long
```

### 记忆/DB 损坏
```bash
# 备份
copy data\database.db data\database.db.bak

# 重建
python -c "from core.db import DB; DB._init()"
```
