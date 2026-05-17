# Changelog

## v2.3.0 (2026-05-17)

### 安全加固
- **fix**: `core/security.py` — `shell=True` 替换为 `shell=False`，消除 shell 解析器逃逸路径
- **fix**: `core/tools.py` — SQL Authorizer 加锁保护，修复多线程下的竞态条件
- **fix**: `core/security.py` — 将 `rm` 加入命令白名单（原代码有专门安全逻辑但 `rm` 不在白名单中，导致死代码）

### 架构优化
- **refactor**: 创建 `core/llm_client.py` 抽象接口，切断 `core/planner.py` 和 `core/reflection.py` 对 `plugins.agent` 的循环依赖
- **fix**: `core/reflection.py` — JSON 正则匹配从惰性改为贪婪，修复嵌套花括号解析失败 Bug

### 测试覆盖
- **test**: 新增 `tests/test_security.py` — 29 个安全测试（L1/L2/L3/全流程/威胁预测/审计）
- **test**: 新增 `tests/test_vision.py` — 10 个视觉模块测试（编码/MIME/回退逻辑/工具封装）
- **test**: 新增 `tests/test_reflection.py` — 11 个反思引擎测试（JSON 解析/LLM 调用/细化循环）
- **test**: 创建 `tests/conftest.py` — 共享 fixture（mock 环境变量/临时路径）
- **chore**: 清除 8 个测试文件的 `sys.path.insert` 样板代码

### 工程化
- **chore**: Git 初始化并推送到 GitHub（`github.com/R1sanpher/riycol-agent`）
- **chore**: `pyproject.toml` — 添加 mypy 类型检查配置 + pytest 标记分类 + 依赖上限锁定
- **chore**: `.gitignore` — 补充 SQLite WAL 文件、models/、生成文件排除

### 测试结果
- 总计 **252 个测试**，全部通过
- 新增 **50 个测试**（之前零覆盖的核心模块）
- 0 回归，0 失败

---

## v2.2.0 (2026-05-17)

- 初始发布版本
- AgentSwarm + ReAct + CrewAI 多智能体系统
- HTTP API + WebSocket 服务器
- Telegram / Discord Bot
- RAG 知识库（ChromaDB + TF-IDF 混合检索）
- Notion 双向同步
- Prompt 模板引擎（38 模板）
- 自我改进学习循环
- 30 个核心模块，137+ 测试
