"""
Token consumption benchmark: OLD vs NEW
========================================
Compares token usage before and after TokenBudget optimization.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.token_counter import count, count_name
from core.token_budget import TokenBudget


def simulate_conversation(turns: int = 6) -> tuple[list, str, str]:
    """Simulate a multi-turn conversation with KB context."""
    system = "你是一个有用的AI助手。"
    kb_context = (
        "人工智能（AI）是计算机科学的一个分支，它研究智能体的设计与构建。"
        "机器学习是AI的子领域，专注于从数据中学习模式。深度学习使用多层神经网络。"
        "自然语言处理（NLP）是AI的重要应用领域。Python是最流行的AI编程语言。"
        "PyTorch和TensorFlow是主流的深度学习框架。大语言模型（LLM）如GPT和Qwen"
        "能够理解和生成自然语言文本，在许多任务上达到人类水平的表现。"
    )
    history = []
    questions = [
        "什么是人工智能？",
        "机器学习和深度学习有什么区别？",
        "Python在AI中为什么这么流行？",
        "什么是大语言模型？",
        "PyTorch和TensorFlow哪个更好？",
        "NLP有哪些主要应用？",
    ]
    answers = [
        "人工智能是计算机科学的一个分支，研究如何构建智能系统。它包括机器学习、自然语言处理、计算机视觉等多个子领域。",
        "机器学习是AI的子领域，专注于从数据中学习。深度学习是机器学习的子集，使用多层神经网络。机器学习需要特征工程，深度学习自动学习特征。",
        "Python因为语法简洁、生态丰富而流行。NumPy、Pandas、Scikit-learn、PyTorch等库构成了完整的数据科学和AI开发生态。",
        "大语言模型是基于Transformer架构的大规模神经网络，通过在海量文本上训练获得语言理解和生成能力。GPT和Qwen是典型代表。",
        "PyTorch更受研究人员欢迎，因为它更Pythonic、调试方便。TensorFlow在生产部署上有优势。现在两者差距在缩小。",
        "NLP应用包括机器翻译、文本摘要、情感分析、问答系统、聊天机器人、信息提取、语音识别等。",
    ]
    for i in range(turns):
        history.append({"role": "user", "content": questions[i]})
        history.append({"role": "assistant", "content": answers[i]})
    return history, system, kb_context


def benchmark_old(history: list, system: str, kb_context: str) -> dict:
    """OLD approach: full KB injected into system, full history, 20-msg trim."""
    msgs = [{"role": "system", "content": system}]
    # Old: inject KB directly into system message
    if kb_context:
        msgs[0]["content"] += f"\n\n【参考资料】\n{kb_context}"
    msgs.extend(history)
    # Old: keep up to 20 messages + system
    if len(msgs) > 20:
        msgs = [msgs[0]] + msgs[-(20 - 1):]

    parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in msgs]
    parts.append("<|im_start|>assistant\n")
    prompt = "".join(parts)
    total = count(prompt)

    # Breakdown (approximate from old behavior)
    sys_tokens = count(msgs[0]["content"])
    hist_tokens = sum(count(m["content"]) for m in msgs[1:])
    overhead = total - sys_tokens - hist_tokens

    return {
        "total_input_tokens": total,
        "system_tokens": sys_tokens,
        "history_tokens": hist_tokens,
        "overhead": max(0, overhead),
        "kb_injected": True,
    }


def benchmark_new(history: list, system: str, kb_context: str, max_output: int = 512) -> dict:
    """NEW approach: TokenBudget with 300-token KB + 4-turn history."""
    budget = TokenBudget(kb_budget=300, max_history_turns=4)
    prompt, info = budget.build_prompt(
        system=system, history=history,
        user_msg=history[-1]["content"] if history else "test",
        kb_context=kb_context, max_output=max_output)
    return info


def print_table(old: dict, new: dict):
    print(f"\n{'='*60}")
    print(f"  Token 消耗对比 (tokenizer: {count_name()})")
    print(f"{'='*60}")
    print(f"  {'指标':<20} {'旧方案':>12} {'新方案':>12} {'节省':>12}")
    print(f"  {'─'*56}")

    rows = [
        ("总输入 Token", old["total_input_tokens"], new["total_input_tokens"]),
        ("系统+KB Token", old.get("system_tokens", 0), new["breakdown"].get("system", 0)),
        ("KB 上下文 Token", old.get("kb_tokens", old.get("system_tokens", 0) - 30),
         new["breakdown"].get("kb", 0)),
        ("历史对话 Token", old.get("history_tokens", 0), new["breakdown"].get("history", 0)),
        ("用户消息 Token", old.get("user_tokens", 0), new["breakdown"].get("user", 0)),
        ("格式开销 Token", old.get("overhead", 0), new["breakdown"].get("overhead", 0)),
        ("预算上限", old.get("budget", "无限制"), new["budget_limit"]),
    ]

    for label, ov, nv in rows:
        if isinstance(ov, int) and isinstance(nv, int):
            if ov > 0:
                saved = ov - nv
                pct = f"{saved / ov * 100:.0f}%"
            else:
                saved = 0
                pct = "—"
            print(f"  {label:<20} {ov:>8}    {nv:>8}    {saved:>6} ({pct})")
        else:
            print(f"  {label:<20} {str(ov):>12} {str(nv):>12}")

    print(f"  {'─'*56}")
    old_total = old["total_input_tokens"]
    new_total = new["total_input_tokens"]
    saved = old_total - new_total
    pct = f"{saved / old_total * 100:.0f}%" if old_total > 0 else "—"
    print(f"  {'★ 总节省':<20} {old_total:>8} →  {new_total:>8}    {saved:>6} ({pct})")

    # Per-request savings at scale
    print(f"\n  ── 规模化估算 ──")
    cost_per_1k = 0.002  # $0.002 per 1K tokens (typical)
    print(f"  每 100 次请求节省: {(saved * 100):,} tokens ≈ ${saved * 100 / 1000 * cost_per_1k:.2f}")
    print(f"  每 10,000 次请求节省: {(saved * 10000):,} tokens ≈ ${saved * 10000 / 1000 * cost_per_1k:.2f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    history, system, kb_context = simulate_conversation(turns=6)
    print(f"\n  模拟场景: {len(history)//2} 轮对话 + KB 上下文 ({len(kb_context)} 字符)")

    old = benchmark_old(history, system, kb_context)
    new = benchmark_new(history, system, kb_context)

    print_table(old, new)
