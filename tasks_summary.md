# Agent 执行模式项目表

## 1. act() — 单轮对话模式
**适用**: 简单问答、知识查询、单步推理
**调用**: `agent.act(task, context)`
**流程**: SafetyCheck → 调用模型 → 返回结果
**模型**: 全部后端 (ollama/deepseek/local)
**特点**: 最轻量，带记忆和历史

## 2. act_with_react() — ReAct 循环模式
**适用**: 需要调用工具的复杂任务（读文件、查数据库、网页搜索）
**调用**: `agent.act_with_react(task, context, max_rounds=5)`
**流程**: Thought → TOOL_CALL → Observation → FINAL_ANSWER 循环
**模型**: 全部后端
**特点**: 支持 7 种内置工具（读/写文件、KB查询、DB查询、WebFetch等），最多 5 轮工具调用

## 3. act_with_plan() — 规划执行模式
**适用**: 多步骤复杂任务（研究报告、代码开发、数据分析）
**调用**: `agent.act_with_plan(task, context, reflect=True/False)`
**流程**: Planner分解 → 逐步骤执行(ReAct/act) → 合成结果 → (可选)反思优化
**模型**: 全部后端
**特点**: 自动规划最多 7 步，支持反射(re)评估

## 4. act_with_reflection() — 反思精炼模式
**适用**: 需要高质量输出（代码审查、方案评审、文章优化）
**调用**: `agent.act_with_reflection(task, context, max_refine_rounds=2)`
**流程**: act() → Reflection.critique() → 修正 → 再次评估（最多 2 轮）
**模型**: 全部后端
**特点**: 自评估+迭代优化，CritiqueResult 含 passes/score/issues/gaps

## 5. act_with_tools() — 函数调用模式
**适用**: DeepSeek 原生工具调用（仅 deepseek 后端）
**调用**: `agent.act_with_tools(task, context)`
**流程**: OpenAI function calling → 循环工具调用 → 合成结果
**模型**: **仅 DeepSeek**（其他模型降级到 act()）
**特点**: 原生 function calling 最稳定，但受限于 deepseek 可用性

---

## 架构对比

| 模式 | Token消耗 | 速度 | 可靠性 | 适合场景 |
|------|-----------|------|--------|----------|
| act() | 低 | 快 | 高 | 日常问答 |
| act_with_react() | 中 | 中 | 中 | 工具调用 |
| act_with_plan() | 高 | 慢 | 中 | 复杂任务 |
| act_with_reflection() | 高 | 慢 | 高 | 质量敏感 |
| act_with_tools() | 中 | 快 | 高 | DeepSeek工具调用 |

> 当前状态：全部 5 种模式已实现，活跃使用中。
> 已知问题：act_with_tools() 仅支持 deepseek（当前 deepseek 未启用），本地模型推荐使用 act_with_react()。
