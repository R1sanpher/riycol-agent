# BUG \u8ffd\u8e2a\u5e93

> \u81ea\u52a8\u7d22\u5f15: bugs \u6309\u4e25\u91cd\u5ea6/\u6a21\u5757/\u72b6\u6001\u5206\u7c7b

## \u7edf\u8ba1

| \u7b49\u7ea7 | \u5df2\u4fee\u590d | \u5f85\u5904\u7406 | \u603b\u8ba1 |
|------|--------|--------|------|
| \ud83d\udd34 \u4e25\u91cd | 17 | 0 | 17 |
| \ud83d\udfe1 \u4e2d\u7b49 | 20 | 0 | 20 |
| \ud83d\udd35 \u5efa\u8bae | 15 | 0 | 15 |
| **\u603b\u8ba1** | **52** | **0** | **52** |

---

## \u5df2\u4fee\u590d (46\u4e2a)

### \ud83d\udd34 \u4e25\u91cd (14)

| ID | \u6a21\u5757 | \u95ee\u9898 | \u4fee\u590d |
|----|------|------|------|
| B001 | handler.py | \u7f29\u8fdb\u5c42\u5c42\u53e0\u52a0\uff0c\u8bed\u6cd5\u9519\u8bef\u65e0\u6cd5\u542f\u52a8 | \u6b63\u5219\u91cd\u5199\u4fee\u590d\u5168\u90e8\u7f29\u8fdb |
| B002 | handler.py | \u65e0 LLM None \u68c0\u67e5\u5bfc\u81f4\u7a7a\u6307\u9488\u5d29\u6e83 | \u6dfb\u52a0 if llm is None: return 503 |
| B003 | handler.py | do_POST \u65e0\u8bf7\u6c42\u4f53\u5b89\u5168\u8bfb\u53d6\uff0c\u7a7a JSON \u5d29\u6e83 | \u6dfb\u52a0 try/except + \u5927\u5c0f\u9650\u5236 |
| B024 | vector_kb.py | 4\u4e2a\u65b9\u6cd5\u7f29\u8fdb\u9519\u8bef\u5d4c\u5957\u5728\u5176\u5b83\u65b9\u6cd5\u5185 | \u7f29\u8fdb\u4fee\u590d\uff0c\u5168\u90e8\u63d0\u5230\u7c7b\u7ea7\u522b |
| B025 | db.py | save_message/get_all_sessions/get_messages \u65b9\u6cd5\u4e0d\u5b58\u5728 | \u6539\u7528 add_msg + \u76f4\u63a5 SQL |
| B026 | db.py | get_samples() \u67e5 training_samples \u8868\u4e3a\u7a7a | \u6539\u4e3a\u76f4\u63a5\u67e5 conversations \u8868 |
| B027 | train.py | Trainer() \u4e0d\u63a5\u53d7 tokenizer \u53c2\u6570 transformers 5.x | \u79fb\u9664 tokenizer \u53c2\u6570 |

### \ud83d\udfe1 \u4e2d\u7b49 (10)

| ID | \u6a21\u5757 | \u95ee\u9898 | \u4fee\u590d |
|----|------|------|------|
| B004 | handler.py | except: \u88f8\u5f02\u5e38\u9759\u9ed8\u541e\u9519\u8bef | \u6539\u4e3a except Exception as e: log |
| B005 | handler.py | socket \u65e0\u8d85\u65f6\uff0c\u957f\u8fde\u63a5\u5361\u6b7b | server.socket.settimeout(120) |
| B006 | bot.py | \u591a\u5904\u5185\u8054 import \u5197\u4f59 | \u63d0\u5347\u5230\u6587\u4ef6\u9876\u90e8 |
| B007 | bot.py | raw = CFG.TELEGRAM_TOKEN \u672a\u4f7f\u7528 | \u79fb\u9664 |
| B008 | stats.py | __init__ \u7f29\u8fdb 12spaces\u21924spaces | \u4fee\u6b63 |
| B009 | stats.py | \u53c2\u6570\u540d wxid\uff08\u5fae\u4fe1\u9057\u7559\uff09\u2192 user_id | \u91cd\u547d\u540d |
| B010 | config.py | 2\u5904\u7f29\u8fdb 8spaces\u21924spaces | \u4fee\u6b63 |
| B011 | kb.py | \u5411\u91cf\u5f15\u64ce\u5931\u8d25\u65f6\u9759\u9ed8\u964d\u7ea7 | \u6dfb\u52a0 warning log |
| B028 | shell | PowerShell from \u5173\u952e\u5b57\u51b2\u7a81 | \u7528 .bat \u6587\u4ef6\u7ed5\u8fc7 |
| B029 | shell | UTF-8 BOM \u5bfc\u81f4 Python SyntaxError | \u7528 WriteAllText \u65e0 BOM \u5199\u5165 |

### \ud83d\udd35 \u5efa\u8bae (14)

| ID | \u6a21\u5757 | \u95ee\u9898 | \u4fee\u590d |
|----|------|------|------|
| B012 | handler.py | docstring qwen_server.py | \u6539\u4e3a handler.py |
| B013 | handler.py | \u793a\u4f8b\u7aef\u53e3 8888 | \u6539\u4e3a 8000 |
| B014 | handler.py | \u672b\u5c3e\u591a\u4f59\u7a7a\u884c | \u6e05\u7406 |
| B015 | handler.py | import json \u672a\u4f7f\u7528 | \u79fb\u9664 |
| B016 | ai.py | import json \u672a\u4f7f\u7528 | \u79fb\u9664 |
| B017 | db.py | import json \u672a\u4f7f\u7528 | \u79fb\u9664 |
| B018 | agent/__init__.py | import json, threading, time \u672a\u4f7f\u7528 | \u79fb\u9664 |
| B019 | telegram/__init__.py | import os \u88ab\u8bef\u5220 | \u6062\u590d |
| B020 | bot.py | \u6587\u4ef6\u540d\u6ce8\u91ca telegram_bot.py \u9519\u8bef | \u79fb\u9664 |
| B021 | bot.py | \u7f3a\u5c11 import time | \u6dfb\u52a0 |
| B022 | bot.py | \u7f3a\u5c11 import random | \u6dfb\u52a0 |
| B023 | bot.py | \u7f3a\u5c11 import os | \u6dfb\u52a0 |
| B030 | gpu | PyTorch 2.12 \u4e0d\u652f\u6301 Blackwell sm_120 | \u7b49 2.13+ \u6216\u7f16\u8bd1\u6e90\u7801 |
| B031 | system | C \u76d8\u7a7a\u95f4\u7206\u6ee1 (100GB/100GB) | \u6e05\u7406 CrashDumps + NVIDIA + \u7f13\u5b58 ~22GB |
| B032 | bot.py | 缩进错误导致发送重试崩溃 | 统一 4 空格缩进 |
| B033 | test_agent.py | 缩进错误导致 pytest 收集失败 | 修正缩进至类级别 |
| B034 | handler.py | chat_history 全局 dict 内存泄漏 | OrderedDict + LRU + MAX_CHAT_SESSIONS |
| B035 | ai.py | AIChat 用户历史 dict 内存泄漏 | OrderedDict + _MAX_USERS=200 LRU |
| B036 | agent | Agent memory 无上限内存泄漏 | MAX_MEMORY=14 自动裁剪 |
| B037 | kb.py | add_text 增量扫描新内容不可见 | 强制 _scan(incremental=False) |
| B038 | kb.py | TF-IDF CJK 分词失败零结果 | 自定义 CJK 字符级+ASCII 词级分词 |
| B039 | config.py | _root 未 resolve 路径比较失败 | .resolve() + tools.py 兜底 |
| B040 | continue.json | API Key 硬编码泄露 | 确认 .gitignore 已排除 |
| B041 | kb.py | 全量扫描性能问题 | 按 mtime 增量扫描 + 后台线程 |
| B042 | db.py | SQLite 多线程写锁 database locked | WAL + timeout=5.0 + busy_timeout=3000 |
| B043 | bot.py | 关键词子串误匹配过滤 | re.search \b 全词匹配 + IGNORECASE |
| B044 | cli,plugin_loader | 裸 except 静默吞系统异常 | except KeyboardInterrupt / except Exception |
| B045 | test_agent.py | MemoryStore 跨测试污染 assert 失败 | autouse fixture clean_agent 隔离 |
| B046 | test_kb.py | test_tool_write 误覆盖 README.md | 改用临时路径 + 事后清理 |

---

## \u5f85\u5904\u7406 (0\u4e2a)

\u5f53\u524d\u65e0\u5f85\u5904\u7406 BUG\u3002

---

## \u7d22\u5f15\u89c4\u5219

`
BUGS.md \u7531\u4ee5\u4e0b\u89c4\u5219\u81ea\u52a8\u7ef4\u62a4:

1. B001-B099: \u4ee3\u7801 BUG
2. B100-B199: \u5b89\u5168\u6f0f\u6d1e
3. B200-B299: \u6027\u80fd\u95ee\u9898
4. B300-B399: \u4ee3\u7801\u98ce\u683c
5. B400-B499: \u6d4b\u8bd5\u8986\u76d6

\u4e25\u91cd\u7b49\u7ea7:
  \ud83d\udd34 \u4e25\u91cd = \u5d29\u6e83/\u6570\u636e\u4e22\u5931/\u5b89\u5168\u6f0f\u6d1e
  \ud83d\udfe1 \u4e2d\u7b49 = \u529f\u80fd\u5f02\u5e38/\u9519\u8bef\u5904\u7406\u7f3a\u5931
  \ud83d\udd35 \u5efa\u8bae = \u4ee3\u7801\u8d28\u91cf/\u53ef\u8bfb\u6027/\u98ce\u683c
`

> \u6700\u540e\u66f4\u65b0: 2026-05-15 | \u5171 46 \u4e2a\u5df2\u4fee\u590d Bug (8\u8f6e\u91cd\u6784)
