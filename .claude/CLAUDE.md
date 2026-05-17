# .claude/ — 子代理定义
# 通用架构/规范见 CLAUDE.md

## 子代理
<!-- 仅列出专有信息；文件路径 & 架构细节见 CLAUDE.md -->

### tg-bot
- 关键文件：`plugins/telegram/bot.py`, `plugins/telegram/ai.py`
- 运行：`python riycol.py run telegram`
- 架构：ThreadPoolExecutor (max 10)，消息超 4096 字符自动分段
- 日志关键字：`Telegram msg`, `Telegram reply`, `TG AI backend`

### agent-debug
- 关键文件：`plugins/agent/__init__.py`, `plugins/agent/crew_agent.py`, `core/planner.py`, `core/reflection.py`
- 运行：`python riycol.py agent run "<task>"` / `python riycol.py crew run "<task>"`
- 测试：`pytest tests/test_agent.py tests/test_retry.py tests/test_planner.py tests/test_memory_upgrade.py -v`

### kb-mgmt
- 知识库：`Bug知识库/` + `Bug知识库/Bug索引.md`
- 学习记录：`.learnings/ERRORS.md`, `.learnings/LEARNINGS.md`, `.learnings/FEATURE_REQUESTS.md`
- 写入工具：`from core.obsidian_writer import obsidian`（`write_note()` 会自动消毒 filename）

### model-ops
- Ollama API：`http://localhost:11434`
- Modelfile：`config/qwen3.Modelfile`
- 更换模型流程：下载 GGUF → `ollama create <name> -f <modelfile>` → 改 `.env`

### pm-spec
- 输出：`SPEC.md`（功能描述与边界、验收标准）
- 触发：新项目/大功能变更，不用于小修小补

### architect
- 输入：`SPEC.md` → 输出：`Architecture-Review.md`（结论 PASS / NEEDS-REWORK）
- 只读，auto-accept edits

### implementer
- 输入：`SPEC.md` + `Architecture-Review.md` → 实现 → 运行单测 → 提交分支
- 遵循 CLAUDE.md 代码风格，auto-accept edits

### tester
- 输入：`SPEC.md` → 输出：`TEST-REPORT.md`（通过/失败明细、覆盖率、修复建议）

### reviewer
- 输入：PR diff → 输出：`Review-Comments.md`（问题+严重级别）
- 只读，auto-accept edits

### server-debug
- 关键文件：`plugins/server/handler.py`, `plugins/server/ws_handler.py`, `static/index.html`
- 运行：`python riycol.py run server`

### pipeline
- 一键启动全流程：pm-spec → architect → implementer → tester → reviewer
- 触发：新功能开发或大变更时
