# 代码健康索引

> 自动追踪: 语法检查 / 导入测试 / 单元测试覆盖率

## 快速状态

```
✅ 语法通过: 21/21 (100%)
✅ 导入正常: 12/12 (100%)
🔲 单元测试:  0/12 (0%)
```

## 模块健康表

| 模块 | 语法 | 导入 | 测试 | 健康度 |
|------|------|------|------|--------|
| `core/config.py` | ✅ | ✅ | - | 🟢 |
| `core/db.py` | ✅ | ✅ | ✅ 18 tests | 🟢 |
| `core/logger.py` | ✅ | ✅ | - | 🟢 |
| `core/plugin_loader.py` | ✅ | ✅ | - | 🟢 |
| `plugins/server/handler.py` | ✅ | ✅ | - | 🟢 |
| `plugins/server/kb.py` | ✅ | ✅ | ✅ 14 tests | 🟢 |
| `plugins/server/vector_kb.py` | ✅ | ✅ | - | 🟢 |
| `plugins/telegram/bot.py` | ✅ | ✅ | - | 🟢 |
| `plugins/telegram/ai.py` | ✅ | ✅ | - | 🟢 |
| `plugins/telegram/stats.py` | ✅ | ✅ | - | 🟢 |
| `plugins/agent/__init__.py` | ✅ | ✅ | ✅ 8 tests | 🟢 |
| `cli/riycol.py` | ✅ | ✅ | - | 🟢 |
| `data/training/train.py` | ✅ | ✅ | - | 🟢 |
| `tests/test_db.py` | ✅ | - | 18 tests | 🟢 |
| `tests/test_kb.py` | ✅ | - | 14 tests | 🟢 |

## 已知问题

| # | 模块 | 问题 | 优先级 | 状态 |
|---|------|------|--------|------|
| - | - | 当前无待处理 | - | ✅ |

## API 端点矩阵

| 端点 | 方法 | 实现 | 测试 | 安全 |
|------|------|------|------|------|
| `/` | GET | ✅ | - | ✅ |
| `/health` | GET | ✅ | - | ✅ |
| `/kb/status` | GET | ✅ | - | ✅ |
| `/kb/upload` | POST | ✅ | - | ✅ 路径限制 |
| `/kb/add` | POST | ✅ | - | ✅ 路径限制 |
| `/kb/delete` | POST | ✅ | - | ✅ 路径限制 |
| `/db/stats` | GET | ✅ | - | ✅ |
| `/clear` | GET | ✅ | - | ✅ |
| `/chat` | POST | ✅ | - | ✅ JWT 就绪 |
| `/chat/stream` | POST | ✅ | - | ✅ JWT 就绪 |

## 运行测试

```bash
# 数据库测试 (18个)
python -m pytest tests/test_db.py -v

# 知识库测试 (14个)
python -m pytest tests/test_kb.py -v

# 全部测试
python -m pytest tests/ -v
```

> 最后更新: 2025-07-17
