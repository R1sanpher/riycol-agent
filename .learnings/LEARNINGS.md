# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260517-62778] insight
**Priority**: low
**Status**: resolved
**Area**: backend
### Summary
Discord bot in a sync project: reuse AIChat from Telegram plugin, run discord.py asyncio in a daemon thread, use `asyncio.to_thread()` for blocking AI calls and `asyncio.run_coroutine_threadsafe()` for external DM delivery. No need to duplicate the 90/10 routing logic.
### Suggested Action
Plugin already created at `plugins/discord/bot.py`. If more async integrations arise, consider extracting a shared async thread helper.

---

## [LRN-20260517-62679] insight
**Priority**: low
**Status**: resolved
**Area**: backend
### Summary
Qwen3-Instruct natively outputs `<think>` blocks even with "output only the command" prompts. Using Ollama `/api/chat` with a system message + `re.sub(r"<think>.*?</think>", ...)` post-processing reliably suppresses verbose thinking (0.6-0.9s response). The `/api/generate` endpoint doesn't support system messages — must use `/api/chat`.
### Suggested Action
nl2cmd implemented at `cli/nl2cmd.py`. The `<think>` stripping pattern (`re.DOTALL`) should be reused wherever Qwen3 output is consumed (already in AIChat for Telegram/Discord).

---

## [LRN-20260517-62544] best_practice
**Priority**: medium
**Status**: resolved
**Area**: config
### Summary
Prompt `chat/code_review` upgraded v1→v2: V3: 项目特定代码审查，引用具体安全检查点和常见漏洞
### Suggested Action
Old version archived to .learnings/prompts_archive/. Monitor performance for regression.

## [LRN-20260517-62544] best_practice
**Priority**: medium
**Status**: resolved
**Area**: config
### Summary
Prompt `chat/bug_fix` upgraded v1→v2: V4: 项目特定调试流程，引用 8 类常见检查点
### Suggested Action
Old version archived to .learnings/prompts_archive/. Monitor performance for regression.

## [LRN-20260515-001] best_practice
**Priority**: high
**Status**: pending
**Area**: infra
### Summary
agent-browser Chrome download blocked in China — need proxy or alternative for `agent_browser` tool
### Suggested Action
Add proxy-aware download or fallback to playwright-based browser automation in core/tools.py

## [LRN-20260517-002] best_practice
**Priority**: high
**Status**: pending
**Area**: backend
### Summary
model_router.py `route()` had dead code: complexity heuristics were unreachable because `ollama` was returned unconditionally. Fixed by evaluating heuristics BEFORE the local-preference return.
### Suggested Action
Monitor routing behavior after fix to confirm deepseek receives appropriate traffic.

## [LRN-20260517-003] best_practice
**Priority**: medium
**Status**: resolved
**Area**: backend
### Summary
planner.py `_parse_plan()` greedy regex `\[[\s\S]*\]` could match wrong bracket pair with nested tool_args. Fixed with bracket-depth matching.
### Suggested Action
None (fixed).

## [LRN-20260517-004] best_practice
**Priority**: medium
**Status**: resolved
**Area**: backend
### Summary
Token tracker was not integrated into streaming methods (`_call_deepseek_stream`, `_call_ollama_stream`). Added usage capture from `stream_options={"include_usage": True}` final chunk.
### Suggested Action
Monitor token_tracker snapshot for streaming calls.

## [LRN-20260517-005] best_practice
**Priority**: medium
**Status**: resolved
**Area**: agent
### Summary
agent `act()` method did not call `record_backend_success/failure` — circuit breakers for model backends were never reset. Added calls in `act()` success/error paths.
### Suggested Action
None (fixed).

## [LRN-20260517-18897] best_practice
**Priority**: medium
**Status**: resolved
**Area**: config
### Summary
Prompt `test/up` upgraded v1→v2: test
### Suggested Action
Old version archived to .learnings/prompts_archive/. Monitor performance for regression.

## [LRN-20260517-20276] best_practice
**Priority**: medium
**Status**: resolved
**Area**: config
### Summary
Prompt `test/up` upgraded v1→v2: test
### Suggested Action
Old version archived to .learnings/prompts_archive/. Monitor performance for regression.

## [LRN-20260517-22821] best_practice
**Priority**: medium
**Status**: resolved
**Area**: config
### Summary
Prompt `test/up` upgraded v1→v2: test
### Suggested Action
Old version archived to .learnings/prompts_archive/. Monitor performance for regression.

## [LRN-20260517-23205] best_practice
**Priority**: medium
**Status**: resolved
**Area**: config
### Summary
Prompt `test/up` upgraded v1→v2: test
### Suggested Action
Old version archived to .learnings/prompts_archive/. Monitor performance for regression.
