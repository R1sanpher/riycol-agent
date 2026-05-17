"""
Reflection — self-critique and refinement for agent outputs.

Critiques agent answers against the original task, identifies gaps/errors,
and triggers refinement when quality is insufficient.
Uses the existing 'self_critique' prompt template (chat/self_critique).
"""
import json, re
from dataclasses import dataclass, field
from core.logger import log


@dataclass
class CritiqueResult:
    passes: bool
    score: float           # 0.0 - 1.0
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    raw_critique: str = ""


class Reflection:
    """Self-critique engine. Reviews agent outputs and triggers refinement."""

    def __init__(self, model: str = "auto", max_refine_rounds: int = 2):
        self.model = model
        self.max_refine_rounds = max_refine_rounds

    def critique(self, task: str, output: str, plan_context: str = "") -> CritiqueResult:
        """Review output against the task and return structured critique."""
        prompt = self._build_critique_prompt(task, output, plan_context)
        try:
            from plugins.agent import raw_llm_call
            raw = raw_llm_call(self.model, self._system_prompt(), prompt, [], temperature=0.3, max_tokens=512)
        except Exception as e:
            log.warn(f"Reflection critique call failed: {e}")
            return CritiqueResult(passes=True, score=0.7, raw_critique="critique unavailable")
        return self._parse_critique(raw)

    def reflect_and_refine(self, task: str, output: str, execute_fn, max_rounds: int = 2) -> str:
        """Full reflect-and-refine loop. Returns best output after max_rounds."""
        for rnd in range(max_rounds):
            critique = self.critique(task, output)
            log.info(f"Reflection round {rnd + 1}: pass={critique.passes}, score={critique.score:.2f}")
            if critique.passes:
                return output
            issues_text = "\n".join(f"- {i}" for i in (critique.issues + critique.gaps))
            refine_prompt = (
                f"原始任务: {task}\n\n当前回答:\n{output[:2000]}\n\n"
                f"审查发现的问题:\n{issues_text}\n\n"
                f"请根据审查意见修订你的回答，给出修正后的完整回答。"
            )
            try:
                output = execute_fn(refine_prompt)
            except Exception:
                break
        return output

    def _system_prompt(self) -> str:
        try:
            from core.prompt_manager import prompts
            return prompts.render("chat", "self_critique")
        except Exception:
            return "You are a rigorous self-critique specialist. Review outputs for errors, gaps, and bias."

    def _build_critique_prompt(self, task: str, output: str, plan_context: str) -> str:
        ctx = f"\nPlan context: {plan_context}" if plan_context else ""
        return (
            f"Task: {task}\n{ctx}\n\n"
            f"Answer to critique:\n{output[:3000]}\n\n"
            f"Evaluate this answer. Output JSON:\n"
            f'{{"passes": true|false, "score": 0.0-1.0, "issues": [...], '
            f'"suggestions": [...], "gaps": [...]}}'
        )

    def _parse_critique(self, raw: str) -> CritiqueResult:
        json_match = re.search(r"\{[\s\S]*?\}", raw)
        if json_match:
            try:
                d = json.loads(json_match.group())
                return CritiqueResult(
                    passes=bool(d.get("passes", True)),
                    score=float(d.get("score", 0.7)),
                    issues=d.get("issues", []),
                    suggestions=d.get("suggestions", []),
                    gaps=d.get("gaps", []),
                    raw_critique=raw,
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        # Fallback: keyword heuristic
        passes = "fail" not in raw.lower() and "issue" not in raw.lower()
        return CritiqueResult(passes=passes, score=0.5, raw_critique=raw)
