---
name: token-guardian
description: Monitor and optimize token usage. Find ghost tokens, prevent context quality decay, survive compaction. Use when conversations get long or Claude seems to forget earlier context.
allowed-tools: Read Bash(python:*)
---

# Token Guardian — Context Window Optimization

Monitor token usage, find waste, and keep context quality high during long sessions.

## What it does

1. **Ghost Token Detection**: Find invisible tokens eating your context budget
2. **Compaction Survival**: Ensure key information survives context compression
3. **Budget Tracking**: Real-time token usage stats
4. **Waste Identification**: Find redundant content, verbose outputs, unused skills

## Commands

Run from project root:
```bash
python .claude/skills/token-guardian/measure.py
```

## Manual checks

When invoked, analyze the current conversation:

### 1. Token Audit
- Count total messages and estimate tokens
- Identify largest messages (usually tool outputs)
- Flag messages that can be summarized

### 2. Context Quality
- Check if key decisions from early in conversation are still present
- Verify CLAUDE.md content is still loaded
- Flag any `[历史摘要]` truncation that lost important info

### 3. Waste Reduction
- Collapse consecutive tool outputs into summaries
- Remove `_error` marked messages from context
- Suggest `/compact` when approaching limit

## riycol-agent specific

- `core/token_budget.py` provides `build_prompt()` with budget tracking
- `core/token_counter.py` provides `count()` for accurate counting
- `Agent.compact_memory()` auto-compacts at MAX_MEMORY=14
- `Agent._strip_error_meta()` removes error markers before LLM calls
