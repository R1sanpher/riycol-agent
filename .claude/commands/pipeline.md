---
description: 一键启动需求→架构→实现→测试→审查→部署→通知全流程
arguments:
  - name: feature_description
    description: 功能描述（用户故事或需求）
    required: true
---
你是技术项目经理，按以下流水线高效执行。原则：人工确认只在关键决策点，其余自动推进。

用户需求：{{ feature_description }}

## 流水线（7 步，3 个人工确认点）

### 第一步 · 技术规格
执行 `/pm-spec "{{ feature_description }}"`

⏸️ **暂停** — 展示 SPEC.md 摘要，等我说「规格确认」后继续。

---

### 第二步 · 架构审查
执行 `/architect`

⏸️ **暂停** — 展示结论（PASS / NEEDS-REWORK），等我说「架构确认」后继续。若 NEEDS-REWORK 则先修复再重新审查。

---

### 第三步 · 实现 + 测试（并行）
**同时并行**执行：

```
/implementer
/tester
```

两个命令均完成后，汇总结果。任一失败则修复后重试，全部通过自动进入第四步。

---

### 第四步 · 代码审查
执行 `/reviewer`

⏸️ **暂停** — 展示问题清单和合并建议，等我说「审查通过」后继续。严重问题必须先修复。

---

### 第五步 · 部署
1. `python riycol.py validate` 配置预检
2. `docker compose -f deploy/docker-compose.yml build`
3. `docker compose -f deploy/docker-compose.yml up -d`
4. `curl -s http://localhost:<PORT>/health` 健康检查
5. 失败则回滚并报告

---

### 第六步 · 推送 & PR
1. `git push origin <当前分支>`
2. 生成 PR 描述（摘要变更、关联 SPEC、测试结果）
3. 输出 PR 链接

---

### 第七步 · 通知
汇总流水线结果：变更摘要、测试通过数、审查结论、部署状态、PR 链接。

---

现在开始执行第一步。
