---
title: "HTTP API 完整参考"
category: "00-项目"
subcategory: "API"
source_section: "00-Project/API"
author: "Riycol Agent"
version: "V2.2"
created: "2026-05-17"
status: "active"
tags: "API, HTTP, SSE, WebSocket, 端点"
---

# HTTP API 完整参考

## 基础信息
- 端口: 8000 (可配)
- 鉴权: Bearer token (API_KEY env)
- 限流: 滑动窗口 60 req/min per IP
- 推理并发: max 2 (ChatQueue Semaphore)

## 端点速查

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/` | No | Web 聊天界面 |
| GET | `/ping` | No | 轻量探活 |
| GET | `/health` | No | 健康检查 |
| GET | `/metrics` | Yes | 指标监控 |
| GET | `/db/stats` | Yes | 数据库统计 |
| GET | `/scheduler` | Yes | 调度器状态 |
| GET | `/memory` | Yes | 记忆存储统计 |
| GET | `/prompts` | Yes | 模板列表 |
| GET | `/kb/status` | No | 知识库状态 |
| GET | `/clear` | No | 清除会话 |
| GET | `/skills` | No | 技能列表 |
| GET | `/ws` | No | WebSocket |
| POST | `/chat` | *No | 非流式聊天 |
| POST | `/chat/stream` | *No | SSE 流式 |
| POST | `/clear` | No | 清除会话 |
| POST | `/kb/upload` | *No | 上传文档 |
| POST | `/kb/add` | *No | 添加文本 |
| POST | `/kb/delete` | *No | 删除文档 |
| POST | `/prompts/reload` | Yes | 热加载模板 |
| POST | `/prompts/preview` | Yes | 渲染预览 |

*No = API_KEY 未配置时无需鉴权

---

## 聊天

### POST /chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "session_id": "abc123",
    "model": "auto",
    "max_tokens": 512,
    "temperature": 0.7,
    "prompt_template": "chat/default"
  }'
```

响应:
```json
{
  "reply": "你好！有什么可以帮你的？",
  "model": "deepseek",
  "tokens": {"prompt": 50, "completion": 15},
  "knowledge": {
    "sources": [],
    "engine": "hybrid_kb",
    "token_cost": 0
  }
}
```

### POST /chat/stream (SSE)

```bash
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "写一个快速排序"}'
```

SSE 事件:
```
data: {"token": "def"}
data: {"token": " quick"}
data: {"token": "_sort"}
data: [DONE]
```

---

## 知识库

### GET /kb/status
```json
{"enabled": true, "engine": "hybrid_kb+chromadb", "documents": 15}
```

### POST /kb/add
```bash
curl -X POST http://localhost:8000/kb/add \
  -H "Content-Type: application/json" \
  -d '{"text": "Riycol Agent 是一个AI平台", "source": "manual"}'
```

### POST /kb/upload
```bash
curl -X POST http://localhost:8000/kb/upload \
  -F "file=@document.md"
```

### POST /kb/delete
```bash
curl -X POST http://localhost:8000/kb/delete \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "document.md"}'
```

---

## 运维

### GET /health
```json
{
  "status": "ok",
  "model": {"ollama": true, "deepseek": true},
  "db": {"messages": 80, "sessions": 3},
  "kb": {"documents": 15, "engine": "hybrid_kb+chromadb"}
}
```

### GET /metrics (需鉴权)
```json
{
  "requests": {"total": 1234, "chat": 800, "stream": 400},
  "latency": {"p50": 1.2, "p90": 3.5, "p99": 8.0, "avg": 2.1},
  "errors": 5,
  "tokens": {"prompt": 50000, "completion": 20000}
}
```

### GET /db/stats (需鉴权)
```json
{"messages": 80, "sessions": 3, "samples": 1392862}
```

### GET /scheduler (需鉴权)
```json
{
  "running": true,
  "task_count": 4,
  "tasks": [
    {"name": "kb_incremental_scan", "run_count": 120, "error_count": 0},
    {"name": "daily_summary", "run_count": 1, "error_count": 0}
  ]
}
```

---

## WebSocket

### 升级
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === 'token') console.log(data.token);
  if (data.type === 'done') console.log('完成');
};
ws.send(JSON.stringify({
  type: 'chat',
  message: '你好',
  session_id: 'ws123'
}));
```

### Origin 验证
- 白名单: `localhost`, `127.0.0.1`
- 其他来源自动拒绝

---

## 鉴权

```bash
# 设置 API_KEY
echo "API_KEY=my-secret" >> .env

# 请求携带
curl -H "Authorization: Bearer my-secret" http://localhost:8000/metrics
```

### 受保护端点
- `/metrics`, `/scheduler`, `/memory`, `/db/stats`, `/prompts`
- `/prompts/reload`, `/prompts/preview`
- 其他端点仅在 API_KEY 配置时要求鉴权
