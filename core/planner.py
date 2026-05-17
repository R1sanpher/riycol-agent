"""
Planner — LLM-driven task decomposition for agent execution.

Produces structured ExecutionPlan from natural language tasks.
Used by Agent.act_with_plan() and crew_agent.decompose_task().
"""
import json, re
from dataclasses import dataclass, field
from typing import Any
from core.logger import log


@dataclass
class PlanStep:
    index: int
    description: str
    tool: str | None = None
    tool_args: dict | None = None
    expected_output: str = ""
    depends_on: list[int] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    task: str
    steps: list[PlanStep]
    raw_plan: str = ""
    model_used: str = "auto"
    tokens_used: int = 0


class Planner:
    """LLM-driven task decomposition planner."""

    def __init__(self, model: str = "auto"):
        self.model = model

    def plan(
        self,
        task: str,
        context: str = "",
        available_tools: list[str] | None = None,
        max_steps: int = 7,
    ) -> ExecutionPlan:
        tools = available_tools or []
        prompt = self._build_planning_prompt(task, tools, context, max_steps)
        try:
            raw = self._call_planner(prompt, task)
        except Exception as e:
            log.warn(f"Planner LLM call failed: {e}, using heuristic fallback")
            return self._heuristic_plan(task, tools)
        steps = self._parse_plan(raw, tools)
        if not steps:
            return self._heuristic_plan(task, tools)
        return ExecutionPlan(task=task, steps=steps, raw_plan=raw, model_used=self.model)

    def _build_planning_prompt(self, task: str, tools: list[str], context: str, max_steps: int) -> str:
        tool_list = ", ".join(tools) if tools else "none"
        ctx = f"\nContext: {context}" if context else ""
        return (
            f"You are a task planning assistant. Decompose the following task into at most {max_steps} steps.\n"
            f"Available tools: [{tool_list}]\n"
            f"For each step, specify: index, description, tool (or null), tool_args (or null), expected_output.\n"
            f"Output as JSON array:\n"
            f'[{{"index":1,"description":"...", "tool":"read_file"|null, '
            f'"tool_args":{{...}}|null, "expected_output":"..."}}]\n'
            f"Rules: assign tools only when necessary. Dependencies are implicit (sequential order).\n"
            f"{ctx}\n"
            f"Task: {task}\n\nPlan:"
        )

    def _parse_plan(self, raw: str, tools: list[str]) -> list[PlanStep]:
        # Try JSON parse — use bracket-depth matching, not greedy regex
        json_str = ""
        start = raw.find("[")
        if start >= 0:
            depth = 0
            for i, ch in enumerate(raw[start:], start):
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        json_str = raw[start:i + 1]
                        break
        if json_str:
            try:
                parsed = json.loads(json_str)
                steps = []
                for item in parsed:
                    tool = item.get("tool")
                    if tool and tool not in tools:
                        tool = None  # ignore invalid tool references
                    steps.append(PlanStep(
                        index=item.get("index", len(steps) + 1),
                        description=item.get("description", ""),
                        tool=tool,
                        tool_args=item.get("tool_args"),
                        expected_output=item.get("expected_output", ""),
                    ))
                return steps
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: line-by-line parse
        steps = []
        for line in raw.splitlines():
            m = re.match(r"(?:STEP\s*)?(\d+)[.:)\s]+(.+)", line.strip(), re.IGNORECASE)
            if m:
                desc = m.group(2).strip()
                steps.append(PlanStep(index=int(m.group(1)), description=desc))
        return steps

    def _call_planner(self, prompt: str, task: str) -> str:
        from core.model_router import route
        model = self.model if self.model != "auto" else route(task)
        from core.llm_client import llm_call
        return llm_call(model, "You are a task planner.", prompt, [], temperature=0.3, max_tokens=512)

    def _heuristic_plan(self, task: str, tools: list[str]) -> ExecutionPlan:
        """Fallback: single-step plan when LLM planning is unavailable."""
        step = PlanStep(index=1, description=task)
        return ExecutionPlan(task=task, steps=[step], model_used="heuristic")
