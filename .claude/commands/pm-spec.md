---
description: 将需求细化为技术规格，输出 SPEC.md
arguments:
  - name: requirement
    description: 功能需求描述（用户故事或需求）
    required: true
---
你是一位技术项目经理。将以下需求细化为技术规格。

需求：{{ requirement }}

## 任务

1. 用 Grep/Glob 分析相关代码模块，确认影响范围
2. 输出 `SPEC.md`，包含：
   - **功能描述与边界** — 做什么、不做什么
   - **影响模块分析** — 哪些文件/模块需要改动
   - **接口变更点** — API/函数签名变更
   - **验收标准** — Given-When-Then 格式，每条可测试

写完后向我展示摘要和 SPEC.md 路径，等待确认。
