---
title: "[Skill] Prompt 模板库"
notion_id: "362a43b0-0cae-8170-9659-c819d680b8bd"
last_synced: "2026-05-17T19:36:58"
notion_edited: "2026-05-16T20:56:00.000Z"
status: "synced"
---

总数: 40个模板, 4个分类

- chat(9): default/tool_use/code_review/bug_fix/memory_palace/self_critique/title_alchemist/riycol_coder/riycol_architect

- vision(1): default(结构化图片分析)

- summary(2): daily(日报)/conversation(对话总结)

- marketing(28): 从Obsidian .md批量导入

引擎: core/prompt_manager.py

- PromptTemplate: {{var}}替换 + version元数据 + to_dict/from_dict

- PromptLibrary: category/name二级注册 + JSON热加载/导出 + 版本管理

- upgrade_template(cat,name,new_template,reason) -> 自动归档旧版 + 记录LEARNINGS.md

- build_messages()/build_chatml() 上下文组装器

- 全局单例: from core.prompt_manager import prompts

新增模板(本次会话): riycol_coder v1(精确代码生成,引用项目规范) / riycol_architect v1(架构决策,3方案格式)

升级模板: code_review v1->v2(项目特定安全检查点) / bug_fix v1->v2(8类常见检查点)
