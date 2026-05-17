"""
Token Budget Manager — controls input token consumption.
=========================================================
Ensures total prompt stays within model context window.
Prioritizes: system prompt > latest messages > KB context > old history.
"""
from core.token_counter import count, count_name
from core.logger import log

# Conservative overhead for ChatML format tokens per message
CHATML_OVERHEAD = 4  # <|im_start|> + <|im_end|> + newlines per message


class TokenBudget:
    def __init__(self, max_input: int = 0, kb_budget: int = 300, max_history_turns: int = 4):
        """
        Args:
            max_input: Max input tokens (0 = auto from N_CTX minus reserve).
            kb_budget: Max tokens for KB context injection.
            max_history_turns: Max conversation turns to keep.
        """
        self.max_input = max_input
        self.kb_budget = kb_budget
        self.max_history_turns = max_history_turns
        self.used = 0
        self.breakdown: dict[str, int] = {}

    def _auto_max(self, max_output: int) -> int:
        from core.config import CFG
        ctx = CFG.N_CTX  # e.g., 2048
        return max(512, ctx - max_output - 256)  # 256 token safety margin

    def build_prompt(self, system: str, history: list[dict],
                     user_msg: str, kb_context: str = "",
                     max_output: int = 512) -> tuple[str, dict]:
        """
        Build a token-budgeted ChatML prompt.
        Returns (formatted_prompt, budget_info).
        """
        limit = self.max_input or self._auto_max(max_output)
        self.used = 0
        self.breakdown = {}

        # 1. System prompt (must fit)
        sys_tokens = count(system)
        self.breakdown["system"] = sys_tokens
        self.used += sys_tokens

        # 2. KB context (truncated to kb_budget)
        kb_tokens = 0
        kb_text = ""
        if kb_context:
            kb_text = self._truncate_text(kb_context, self.kb_budget)
            kb_tokens = count(kb_text)
            self.breakdown["kb"] = kb_tokens
            self.used += kb_tokens

        # 3. Latest messages (most recent first, stop when budget exceeded)
        remaining = limit - self.used - count(user_msg) - 50  # 50 token safety
        hist_msgs, hist_tokens = self._select_history(history, remaining,
                                                       self.max_history_turns)
        self.breakdown["history"] = hist_tokens
        self.used += hist_tokens

        # 4. User message
        user_tokens = count(user_msg)
        self.breakdown["user"] = user_tokens
        self.used += user_tokens

        # 5. Build ChatML
        msgs = [{"role": "system", "content": system}]
        if kb_text:
            msgs.append({"role": "system", "content": f"参考资料:\n{kb_text}"})
        msgs.extend(hist_msgs)
        msgs.append({"role": "user", "content": user_msg})

        parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in msgs]
        parts.append("<|im_start|>assistant\n")
        prompt = "".join(parts)

        overhead = count(prompt) - self.used
        self.breakdown["overhead"] = max(0, overhead)
        self.used += overhead

        info = {
            "total_input_tokens": self.used,
            "budget_limit": limit,
            "tokenizer": count_name(),
            "breakdown": self.breakdown,
            "truncated": self.used > limit,
        }
        if self.used > limit * 1.1:
            log.warn(f"Token budget exceeded: {self.used}/{limit}")

        return prompt, info

    def _select_history(self, history: list[dict], max_tokens: int,
                        max_turns: int) -> tuple[list[dict], int]:
        """Select recent messages that fit within token budget."""
        if not history or max_tokens <= 0:
            return [], 0

        max_msgs = max_turns * 2  # Each turn = user + assistant
        candidates = history[-max_msgs:]

        # Build in reverse then flip — O(n) instead of O(n²) with insert(0, ...)
        selected_rev = []
        used = 0
        for msg in reversed(candidates):
            t = count(msg["content"]) + CHATML_OVERHEAD
            if used + t > max_tokens and selected_rev:
                break
            selected_rev.append(msg)
            used += t
        selected_rev.reverse()
        return selected_rev, used

    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to roughly max_tokens by character ratio."""
        if max_tokens <= 0:
            return ""
        # Rough: 1 token ≈ 2 chars for Chinese, 4 chars for English
        max_chars = max_tokens * 2
        if len(text) <= max_chars:
            return text
        # Try to break at paragraph boundary
        truncated = text[:max_chars]
        last_break = max(truncated.rfind("\n\n"), truncated.rfind("\n"))
        if last_break > max_chars // 2:
            truncated = truncated[:last_break]
        return truncated.strip()
