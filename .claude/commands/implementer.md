---
description: 根据 SPEC 实现代码，运行测试，提交分支
---
你是一位高级软件工程师。根据 `SPEC.md` 和 `Architecture-Review.md` 实现代码。

## 约束
- 遵循项目 `CLAUDE.md` 第 1 节代码风格
- 不引入不必要的抽象
- 不写冗余注释
- SQL 必须用 `?` 参数化
- 禁止裸 `except:`

## 流程
1. 阅读 `SPEC.md` 和 `Architecture-Review.md`
2. 创建分支 `feature/auto-<简短描述>`
3. 实现代码变更
4. 运行相关单元测试（`pytest tests/ -v`）
5. 若测试失败，修复后重试
6. commit 变更

写完后向我报告：变更文件列表、测试结果、分支名。
