---
title: "CLI 命令完整参考"
category: "00-项目"
subcategory: "操作"
source_section: "00-Project/Operations"
author: "Riycol Agent"
version: "V2.2"
created: "2026-05-17"
status: "active"
tags: "CLI, 命令, 操作, 开发"
---

# CLI 命令完整参考

## 所有子命令一览

```
riycol run       — 启动服务
riycol agent     — Agent 操作
riycol crew      — 多角色协作
riycol sync      — 同步 Notion/会话
riycol model     — 模型管理
riycol data      — 数据管理
riycol finetune  — 微调管道
riycol kb        — 知识库
riycol db        — 数据库统计
riycol memory    — 记忆存储
riycol scheduler — 调度器状态
riycol plugin    — 插件管理
riycol validate  — 配置检查
riycol version   — 版本号
riycol help      — 帮助
```

---

## run — 启动服务

```bash
python riycol.py run                  # 全部服务
python riycol.py run server           # HTTP API (端口 8000)
python riycol.py run telegram         # Telegram Bot
python riycol.py run agent            # Agent Swarm 后台
```

---

## agent — Agent 操作

```bash
# 列出 Agent
python riycol.py agent list

# 单 Agent 执行任务
python riycol.py agent run "分析 core/db.py 有没有性能问题"

# 多 Agent 并行执行
python riycol.py agent run "对比三个 Python web 框架的优缺点" --parallel

# 带反思精炼
python riycol.py agent run "找出项目所有安全隐患" --reflect

# 带记忆上下文
python riycol.py agent review "继续上次的工作"
```

### 五个执行模式 (程序化)

| 模式 | 方法 | 说明 |
|------|------|------|
| 直接回答 | `agent.act(task)` | 单轮，无工具 |
| Function Calling | `agent.act_with_tools(task)` | DeepSeek 专用 |
| ReAct | `agent.act_with_react(task)` | 所有后端 |
| 规划执行 | `agent.act_with_plan(task)` | Plan→Execute→Synthesize |
| 反思精炼 | `agent.act_with_reflection(task)` | Act→Critique→Refine |

---

## crew — 多角色协作

```bash
# 列出 5 个角色
python riycol.py crew roles
# → riycol, reviewer, researcher, writer, coder

# 自动分配角色
python riycol.py crew run "写一篇 Rust vs Go 性能对比报告"

# 指定角色
python riycol.py crew run "审查代码安全" --roles riycol reviewer coder

# 指定模型
python riycol.py crew run "..." --model deepseek
```

---

## sync — 同步

```bash
# 全同步
python riycol.py sync all

# Notion → 本地
python riycol.py sync notion --direction pull

# 本地 → Notion
python riycol.py sync notion --direction push

# 双向
python riycol.py sync notion --direction bidirectional

# 注册跨会话任务
python riycol.py sync session --task "正在修复 Bug #42"

# 查看同步状态
python riycol.py sync status
```

---

## model — 模型管理

```bash
python riycol.py model list              # 列出 6 个可用模型
python riycol.py model check             # 检查当前模型可用性
python riycol.py model download qwen3-8b # 下载 GGUF
```

### 模型目录

| Key | 模型 | 大小 | Context |
|-----|------|------|---------|
| gemma4-e4b | Gemma 4 E4B Q4_K_M | 5.5GB | 128K |
| qwen2.5-1.5b | Qwen2.5 1.5B Q4_K_M | 1.1GB | 2048 |
| qwen2.5-3b | Qwen2.5 3B Q4_K_M | 2.0GB | 4096 |
| qwen2.5-7b | Qwen2.5 7B Q4_K_M | 4.4GB | 8192 |
| llama3.2-3b | Llama 3.2 3B Q4_K_M | 2.0GB | 4096 |

---

## data / finetune — 数据与微调

```bash
# 数据统计
python riycol.py data stats

# 构建训练数据
python riycol.py data build --limit 5000

# 导出
python riycol.py data export

# 微调管道 (7 步)
python riycol.py finetune stats      # 状态
python riycol.py finetune prepare    # 数据准备
python riycol.py finetune clean      # 清洗
python riycol.py finetune validate   # 校验
python riycol.py finetune convert    # 格式转换 (Alpaca + ShareGPT)
python riycol.py finetune config     # 生成训练配置
python riycol.py finetune all        # 完整流程
```

---

## 运维命令

```bash
python riycol.py validate      # 全面配置检查
python riycol.py version       # 版本号 (v2.2.0)
python riycol.py db            # 数据库统计 (消息/会话/样本数)
python riycol.py memory        # Agent 记忆统计 (按 agent 分组)
python riycol.py scheduler     # 调度器状态 (任务列表/运行次数)
python riycol.py plugin list   # 插件列表
python riycol.py kb refresh    # 重新扫描知识库
python riycol.py kb stats      # 知识库统计
```

---

## 开发命令

```bash
# 安装依赖
pip install ".[dev]"          # 测试 + lint
pip install ".[all]"          # 全部

# 测试
pytest tests/ -v                                         # 全部
pytest tests/ -v --ignore=tests/test_e2e.py              # 跳过 e2e
pytest tests/test_agent.py -v                             # 单文件
pytest tests/test_agent.py::TestAgent::test_act -v        # 单测试

# Lint
python -m ruff check core/ plugins/ cli/ tests/ --ignore E501
python -m ruff check core/ plugins/ cli/ tests/ --ignore E501 --fix
```
