---
title: "Agent 系统完整指南"
category: "00-项目"
subcategory: "核心系统"
source_section: "00-Project/Core"
author: "Riycol Agent"
version: "V2.2"
created: "2026-05-17"
status: "active"
tags: "Agent, ReAct, 多Agent, 规划, 反思"
---

# Agent 系统完整指南

## 架构

```
plugins/agent/
├── __init__.py       # Agent + AgentSwarm + raw_llm_call (750行)
└── crew_agent.py     # CrewAI 多角色协作 (337行)

core/
├── planner.py        # 任务规划引擎
├── reflection.py     # 自我批判引擎
├── tools.py          # 8 内置工具 + 注册表
├── memory_store.py   # 持久记忆 (SQLite)
├── memory_vector.py  # 语义向量记忆 (ChromaDB)
└── retry.py          # 重试 + 断路器
```

## Agent 类 (plugins/agent/__init__.py)

### 初始化

```python
from plugins.agent import Agent

agent = Agent(
    name="助手",
    role="通用助手",
    model="auto",                      # auto|deepseek|ollama|local|mock
    system_prompt=("chat", "default")  # 或 "原始字符串" 或 None
)
```

### 五个执行模式

| # | 方法 | 流程 | 后端 |
|---|------|------|------|
| 1 | `act(task, context)` | 单轮直接回答 | 全部 |
| 2 | `act_with_tools(task, context, max_rounds=3)` | OpenAI function calling | DeepSeek |
| 3 | `act_with_react(task, context, max_rounds=5)` | Thought→TOOL_CALL→Observation→FINAL_ANSWER | 全部 |
| 4 | `act_with_plan(task, max_rounds=5, reflect=False)` | Plan→Execute→Synthesize | 全部 |
| 5 | `act_with_reflection(task, max_refine_rounds=2)` | Act→Critique→Refine | 全部 |

### 记忆管理

```python
# 自动持久化
agent.act("hello")  # 自动保存对话到 memory_store

# 手动检查
agent.last_reply_was_error  # → True/False

# 记忆压缩 (超过 MAX_MEMORY=14 时自动触发)
agent.compact_memory()
# → LLM 摘要最旧消息，保留最近 4 条
# → 摘要存到 conversation_summary key
# → 下次加载时自动注入 [历史摘要] 到上下文
```

### 错误处理

```python
# 错误回复带 _error 标记
{"role": "assistant", "content": "...", "_error": True}

# 保存时自动过滤 _error 消息
# 发送给 LLM 前通过 _strip_error_meta() 去除内部标记
# API 调用带 @retry(max_attempts=3) 装饰器
# 断路器开放时返回友好消息
```

---

## ReAct 流程详解

```
用户: "读取.env文件并解释配置"
    ↓
Agent.act_with_react(task)
    ↓
Round 1: Thought: 需要读取.env文件
         TOOL_CALL: read_file
         ARGUMENTS: {"filepath": ".env"}
         Observation: [文件内容...]
    ↓
Round 2: Thought: 已读取内容，可以解释
         FINAL_ANSWER: 该文件包含以下配置...
```

### 解析格式
- `TOOL_CALL: <tool_name>` — 调用工具
- `ARGUMENTS: <json>` — JSON 参数
- `FINAL_ANSWER:` — 最终回答
- 观察截断 2000 字符
- 工具错误自动反馈

---

## AgentSwarm 多智能体

### 架构
```
         任务输入
            ↓
     Planner 分解任务
            ↓
     角色分配 (5 角色)
     ┌───┬───┬───┬───┐
     Riycol  Reviewer  Researcher  Writer  Coder
     └───┴───┴───┴───┘
            ↓
     parallel=True → ThreadPoolExecutor(4)
     parallel=False → 顺序执行，传递上下文
            ↓
     _synthesize 综合产出
            ↓
         最终回答
```

### 程序化调用

```python
from plugins.agent import AgentSwarm

swarm = AgentSwarm()

# 自动角色分配 + 并行
result = swarm.run("写一份 Python Async 框架对比报告", parallel=True)

# 带记忆上下文
result = swarm.run_with_review("继续上次的分析", memory_context="...")
```

### 自主任务 (调度器注册)
| 任务 | 时间 | 功能 |
|------|------|------|
| daily_summary | 08:00 | 生成昨日对话摘要 |
| kb_health | 每小时 | KB 健康检查 |
| memory_cleanup | 03:00 | 清理过期记忆 |

---

## CrewAI 多角色 (crew_agent.py)

### 5 个角色定义

| 角色 | 职责 |
|------|------|
| riycol | 全能助手，协调综合 |
| reviewer | 审查输出质量、一致性和完整性 |
| researcher | 信息收集、背景研究 |
| writer | 写作、内容生成 |
| coder | 代码编写、调试、技术分析 |

### CLI 用法

```bash
python riycol.py crew run "分析项目安全性" --roles riycol reviewer coder
python riycol.py crew roles  # 列出所有角色
```

### 任务分解
- LLM 驱动: 通过 Planner 分解复杂任务
- 关键词回退: LLM 不可用时使用关键词启发式
- 多步骤末尾自动加 reviewer

---

## 规划引擎 (core/planner.py)

### 数据结构

```python
@dataclass
class PlanStep:
    index: int           # 步骤序号
    description: str     # 步骤描述
    tool: str | None     # 需要用的工具名
    tool_args: dict      # 工具参数
    expected_output: str # 期望产出
    depends_on: list[int] # 依赖的步骤序号

@dataclass
class ExecutionPlan:
    task: str
    steps: list[PlanStep]
    raw_plan: str        # LLM 原始输出
```

### JSON 解析优先 + 正则回退

```python
planner = Planner(model="auto")
plan = planner.plan(
    task="重构 core/db.py 模块",
    available_tools=["read_file", "write_file", "db_query"],
    max_steps=7
)
```

---

## 反思引擎 (core/reflection.py)

```python
reflection = Reflection(model="auto", max_refine_rounds=2)

# 审查输出
critique = reflection.critique(task, output)
# → {passes: bool, score: 0-1, issues: [...], suggestions: [...]}

# 完整循环
result = reflection.reflect_and_refine(task, initial_output, execute_fn)
```

### CritiqueResult
| 字段 | 说明 |
|------|------|
| passes | 是否通过质量检查 |
| score | 0.0-1.0 质量评分 |
| issues | 发现的问题列表 |
| suggestions | 改进建议 |
| gaps | 遗漏的内容 |
| raw_critique | LLM 原始审查输出 |

---

## 工具系统 (core/tools.py)

### 8 个内置工具

| 工具 | 用途 | 安全措施 |
|------|------|---------|
| read_file | 读取项目文件 | 路径沙箱 |
| write_file | 写入文件 | 路径沙箱 |
| search_kb | 搜索知识库 | 只读 |
| db_query | SQL 查询 | set_authorizer 白名单 |
| get_time | 服务器时间 | 纯函数 |
| web_fetch | 抓取网页 | 超时 10s |
| agent_browser | 浏览器自动化 | subprocess |
| describe_image | 图片分析 | 文件验证 |

### 工具四要素

```python
Tool(
    name_for_human="Read File",    # 人类可读
    name_for_model="read_file",    # 模型调用
    description="Read a text file",
    parameters={...}               # JSON Schema
)
```

### 添加新工具

```python
from core.tools import Tool, tool_registry, _builtin_tools

def tool_my_func(param: str) -> dict:
    return {"result": param}

_builtin_tools.append(
    Tool("my_func", "Description",
         {"type": "object", "properties": {
             "param": {"type": "string"}
         }, "required": ["param"]},
         tool_my_func, name_for_human="My Function")
)
```

---

## 共享 LLM 调用

```python
from plugins.agent import raw_llm_call

# Agent, Planner, Reflection 共享此函数
reply = raw_llm_call(
    model="deepseek",
    system="You are a helpful assistant.",
    user="Hello",
    history=[],
    temperature=0.3,
    max_tokens=1024
)
# → 带 @retry(max_attempts=3) 装饰器
```

---

## Token 预算管理

```python
from core.token_budget import TokenBudget

budget = TokenBudget(max_input=0, kb_budget=300, max_history_turns=4)
prompt, info = budget.build_prompt(
    system="You are...",
    history=[...],
    user_msg="hello",
    kb_context="...",
)
# → ChatML 格式化字符串
# → {total_input_tokens, tokenizer, truncated, breakdown}
```

### 优先级: System > KB > 最新 History > User
