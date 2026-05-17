# Riycol Agent — Multi-Agent AI Framework

多功能AI服务平台：本地 gemma4-e4b Ollama 推理 + Telegram 机器人 + 统一 Agent + 知识库 + 数据蒸馏

## 快速开始

### 1. 准备环境
```bash
# 安装运行时依赖
pip install openai requests chromadb

# 或完整安装（含本地LLM支持）
pip install ".[all]"

# 配置环境变量 (复制 .env.example 为 .env 并填写)
```

### 2. 启动服务
```bash
# 启动所有服务
python riycol.py run all

# 或单独启动:
python riycol.py run server       # HTTP API + Web UI
python riycol.py run telegram     # Telegram bot (需配置TOKEN)
python riycol.py run agent        # Agent swarm系统
```

### 3. 验证配置
```bash
python riycol.py validate         # 检查所有配置项
```

### 4. API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Web 聊天界面 |
| GET | `/health` | 健康检查 (model/db/kb) |
| GET | `/metrics` | 指标监控 |
| POST | `/chat` | 非流式聊天 |
| POST | `/chat/stream` | SSE 流式聊天 |
| POST | `/kb/add` | 添加文本到知识库 |
| POST | `/kb/upload` | 上传文档 |
| POST | `/kb/delete` | 删除文档 |
| GET | `/kb/status` | 知识库状态 |
| GET | `/db/stats` | 数据库统计 (需auth) |
| GET | `/scheduler` | 任务调度器 |
| GET | `/memory` | Agent 记忆存储 |
| GET | `/prompts` | Prompt 模板管理（需鉴权） |

### 5. API 鉴权（可选）
```bash
set API_KEY=my-secret-key
# 请求时携带: Authorization: Bearer my-secret-key
```

## 功能模块

### 本地推理服务 (Server)
- Ollama 运行 gemma4-e4b 模型 (7.5B Q4_K_M)
- 后端可选：ollama / deepseek / local (llama-cpp)
- 流式输出 (SSE)、多轮对话、会话隔离
- 限流保护 + API Key 鉴权 + LRU 会话管理

### Telegram 机器人
- 多后端支持：Ollama 本地 / DeepSeek API / llama-cpp，自动路由
- 异步并发处理 (ThreadPoolExecutor)
- 长文本自动分段 + typing indicator + 指数退避重试

### 统一智能体 (Agent)
- 单一全能 Agent: 融合分析/研究/写作/审查/记忆五种能力
- 双模式: run() / run_with_review() 带自审
- Tool-use: 文件读写/KB搜索/DB查询/网页抓取
- 持久记忆: 重启不丢失
- 自主任务: 每日摘要/KB巡检/记忆清理

### 知识库 (RAG)
- TF-IDF 向量检索 (纯 Python) + ChromaDB 语义搜索
- 可配置 Embedding: all-MiniLM / bge-small-zh / 自定义
- CJK 字符级分词 + 增量扫描

### 自主任务引擎
- 进程内调度器: interval / daily cron
- 每日对话摘要 (08:00) + KB健康巡检 (每小时)

## CLI 命令

```bash
riycol run [all|server|telegram|agent]
riycol agent list|run|review
riycol data stats|build|export
riycol kb refresh|stats
riycol validate|version|scheduler|memory
```

## 配置 (.env)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OLLAMA_MODEL` | 本地主力模型 | gemma4-e4b |
| `DEEPSEEK_API_KEY` | DeepSeek API Key（兜底） | — |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | — |
| `TG_MODEL` | TG Bot 后端选择 | auto |
| `API_KEY` | HTTP API 鉴权 | — |
| `EMBEDDING_MODEL` | 向量模型 | all-MiniLM-L6-v2 |
| `MAX_CHAT_SESSIONS` | 最大会话数 | 500 |

---
*v2.2.0 — 2026-05-16*