"""
CrewAI Integration — Multi-role collaboration with task decomposition.
======================================================================
Wraps the existing Riycol LLM backends as CrewAI-compatible LLMs,
provides crew role definitions, task decomposition, and orchestration.

Usage:
    python riycol.py crew run "<task>"
    python riycol.py crew run "<task>" --roles riycol,reviewer
"""
import os, sys
from typing import Any
from collections.abc import Callable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.logger import log
from core.config import CFG
from core.memory_store import memory_store
from core.model_router import get_ollama_url


# ============================================================
# LLM Adapter — makes our backends CrewAI-compatible
# ============================================================

class RiycolLLM:
    """CrewAI-compatible LLM wrapping our Ollama/DeepSeek/local backends."""

    def __init__(self, model: str = "auto"):
        self.model = self._resolve(model)

    def _resolve(self, model: str) -> str:
        if model != "auto":
            return model
        from core.model_router import get_available_models
        avail = get_available_models()
        if avail.get("ollama"):
            return "ollama"
        if avail.get("deepseek"):
            return "deepseek"
        return "local"

    def call(self, messages: list[dict], stop: list[str] | None = None, **kwargs) -> str:
        """
        CrewAI calls this with a list of messages. We dispatch to the correct backend.
        """
        system = ""
        user = ""
        history: list[dict] = []

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
            if role == "system":
                system = str(content)
            elif role == "user":
                user = str(content)
            elif role in ("assistant", "function", "tool"):
                history.append({"role": str(role), "content": str(content)})

        if self.model == "deepseek":
            return self._call_deepseek(system, user, history, stop)
        elif self.model == "ollama":
            return self._call_ollama(system, user, history, stop)
        else:
            return self._call_local(system, user, history, stop)

    def _call_deepseek(self, system: str, user: str, history: list, stop=None) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=CFG.DEEPSEEK_KEY, base_url=CFG.DEEPSEEK_URL)
        msgs = [{"role": "system", "content": system}]
        msgs.extend(history)
        msgs.append({"role": "user", "content": user})
        resp = client.chat.completions.create(
            model="deepseek-chat", messages=msgs, temperature=0.7)
        return resp.choices[0].message.content or ""

    def _call_ollama(self, system: str, user: str, history: list, stop=None) -> str:
        from openai import OpenAI
        client = OpenAI(base_url=f"{get_ollama_url()}/v1", api_key="ollama")
        msgs = [{"role": "system", "content": system}]
        msgs.extend(history)
        msgs.append({"role": "user", "content": user})
        resp = client.chat.completions.create(
            model=CFG.OLLAMA_MODEL, messages=msgs, temperature=0.7)
        return resp.choices[0].message.content or ""

    def _call_local(self, system: str, user: str, history: list, stop=None) -> str:
        from core.llm_bridge import is_loaded, generate
        if not is_loaded():
            return "[CrewAI] Local model not loaded"
        parts = [f"<|im_start|>system\n{system}<|im_end|>\n"]
        for m in history:
            parts.append(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n")
        parts.append(f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n")
        resp = generate("".join(parts), max_tokens=1024, temperature=0.7)
        return str(resp.get("choices", [{}])[0].get("text", "")).strip()


# ============================================================
# Role Definitions
# ============================================================

CREW_ROLES: dict[str, tuple[str, str]] = {
    "riycol": (
        "Riycol — 全能AI助手",
        """你是 Riycol，全能 AI 助手，融合分析、研究、写作、审查、记忆五种能力。
- 分析拆解问题，研究背景知识，组织流畅中文回复
- 代码示例标注语言，不确定时诚实说明
- 与其他角色协作时：接收任务后独立完成，交付前自审一遍
- 执行角色: 是团队的中坚力量，任何角色完成不了的来找你"""
    ),
    "reviewer": (
        "Riycol Reviewer — 质量审查专家",
        """你是 Riycol Reviewer，专门审查和优化他人产出的 AI。
- 检查逻辑漏洞、事实错误、遗漏点、表达不清
- 发现错误不自己修，标注问题并退回原执行者修改
- 质量通过则标注 PASS，追加改进建议
- 执行角色: 所有产出必须经过你的审查才能交付用户"""
    ),
    "researcher": (
        "Riycol Researcher — 信息研究员",
        """你是 Riycol Researcher，专门搜集、整理和验证信息的 AI。
- 通过网络搜索、知识库查询收集相关信息
- 区分事实与观点，标注信息来源和可信度
- 输出结构化研究报告，含摘要、证据、不确定项
- 执行角色: 当任务需要外部信息或深度调研时由你先行"""
    ),
    "writer": (
        "Riycol Writer — 内容写手",
        """你是 Riycol Writer，专注于高质量文字输出的 AI。
- 根据简报和目标受众调整文风：技术文档、营销文案、教育内容皆可
- 结构清晰、段落流畅、无废话
- 交付后接受 Reviewer 反馈并修改
- 执行角色: 所有面向用户的文字产出由你执笔"""
    ),
    "coder": (
        "Riycol Coder — 编码专家",
        """你是 Riycol Coder，专门编写和调试代码的 AI。
- 先理解需求和现有代码架构，再动手
- 代码干净、安全、可测试，遵循项目风格
- 涉及 DB/文件系统的操作优先考虑数据安全
- 执行角色: 所有编码/调试任务由你处理"""
    ),
}


# ============================================================
# Task Decomposition
# ============================================================

def decompose_task(task: str) -> list[dict[str, str]]:
    """Decompose a complex task into subtasks with assigned roles.

    Uses a simple heuristic + the LLM to break down work.
    Returns list of {role, description, expected_output}.
    """
    # Heuristic: task complexity hints
    has_code = any(kw in task.lower() for kw in ("代码", "bug", "debug", "function", "写一个", "实现"))
    has_research = any(kw in task.lower() for kw in ("调研", "研究", "分析", "对比", "评估", "市场"))
    has_writing = any(kw in task.lower() for kw in ("写", "文案", "文章", "报告", "博客", "总结"))
    is_complex = len(task) > 200 or task.count("\n") > 3 or task.count("?") > 2

    if not is_complex and not (has_code or has_research or has_writing):
        # Simple task — single agent
        return [{"role": "riycol", "description": task,
                 "expected_output": "完整的中文回答"}]

    subtasks: list[dict] = []

    if has_research:
        subtasks.append({
            "role": "researcher",
            "description": f"搜集并整理以下相关信息: {task}",
            "expected_output": "结构化研究报告，含关键数据、信息来源和不确定项",
        })

    if has_code:
        subtasks.append({
            "role": "coder",
            "description": f"根据需求和现有架构编写代码: {task}",
            "expected_output": "可运行的代码，含必要的错误处理和注释",
        })

    if has_writing:
        subtasks.append({
            "role": "writer",
            "description": f"根据研究结果撰写内容: {task}",
            "expected_output": "高质量中文内容，结构清晰、格式规范",
        })

    if not subtasks:
        # Fallback: riycol does everything
        subtasks.append({
            "role": "riycol",
            "description": task,
            "expected_output": "完整的中文回答",
        })

    # Always add reviewer at the end for multi-step tasks
    if len(subtasks) > 1:
        subtasks.append({
            "role": "reviewer",
            "description": "审查所有前序步骤的产出，检查逻辑、事实、格式，标注问题或 PASS",
            "expected_output": "审查报告: 每项产出标注 PASS/REJECT + 具体问题 + 修改建议",
        })

    return subtasks


# ============================================================
# Crew Builder & Runner
# ============================================================

class RiycolCrew:
    """Build and run a CrewAI crew with specified roles."""

    def __init__(self, model: str = "auto", verbose: bool = False):
        self.llm = RiycolLLM(model)
        self.verbose = verbose

    def run(self, task: str, roles: list[str] | None = None, process: str = "sequential") -> dict:
        """
        Run a crew on the given task.

        Args:
            task: The task description
            roles: Which roles to use (default: auto-detect via decompose_task)
            process: "sequential" (default) or "hierarchical"

        Returns dict with {status, result, steps, roles_used}
        """
        if roles is None:
            subtasks = decompose_task(task)
        else:
            subtasks = [
                {"role": r, "description": task,
                 "expected_output": "完整的中文回答" if i == len(roles) - 1 else f"{r} 角色的产出"}
                for i, r in enumerate(roles)
            ]

        steps: list[dict] = []
        outputs: dict[str, str] = {}

        for i, st in enumerate(subtasks):
            role_name = st["role"]
            role_goal, role_backstory = CREW_ROLES.get(
                role_name, (f"{role_name} Agent", f"你是 {role_name}，负责完成分配的任务。"))

            context = ""
            if outputs:
                context = "\n\n--- 前序产出 ---\n"
                for prev_role, prev_output in outputs.items():
                    context += f"[{prev_role}]: {prev_output[:1500]}\n"

            prompt = f"{role_backstory}\n\n## 任务\n{st['description']}\n{context}\n\n## 期望产出\n{st['expected_output']}\n\n请完成你的工作。"

            messages = [
                {"role": "system", "content": f"角色: {role_goal}\n{role_backstory}"},
                {"role": "user", "content": prompt},
            ]

            result = self.llm.call(messages)

            outputs[role_name] = result
            steps.append({
                "step": i + 1,
                "role": role_name,
                "task": st["description"][:200],
                "output": result[:1000],
            })

            if self.verbose:
                log.info(f"[Crew] Step {i + 1}/{len(subtasks)}: {role_name} → {len(result)} chars")

        # Final: riycol synthesizes if multiple outputs
        if len(outputs) > 1:
            synthesis = self._synthesize(task, outputs)
            final = synthesis
        else:
            final = list(outputs.values())[0]

        memory_store.put("crew", "last_run", {
            "task": task[:200],
            "roles_used": list(outputs.keys()),
            "steps": len(steps),
            "final_result": final[:500],
        })

        return {
            "status": "ok",
            "result": final,
            "steps": steps,
            "roles_used": list(outputs.keys()),
        }

    def _synthesize(self, task: str, outputs: dict[str, str]) -> str:
        """Synthesize multiple role outputs into one coherent response."""
        parts = "\n\n".join(f"## {role} 的产出\n{out[:2000]}" for role, out in outputs.items())
        prompt = f"请将以下多角色协作的产出综合成一份完整回答:\n\n原始任务: {task}\n\n{parts}\n\n综合回答:"
        return self.llm.call([
            {"role": "system", "content": "你是 Riycol，负责将团队产出综合成最终回答。"},
            {"role": "user", "content": prompt},
        ])


# ============================================================
# Singleton & Plugin Entry
# ============================================================

_crew: RiycolCrew | None = None


def get_crew(model: str = "auto") -> RiycolCrew:
    global _crew
    if _crew is None:
        _crew = RiycolCrew(model=model, verbose=CFG.DEBUG)
    return _crew


def list_roles() -> list[dict]:
    """List available crew roles with their goals."""
    return [
        {"name": name, "goal": goal, "backstory": backstory[:100] + "..."}
        for name, (goal, backstory) in CREW_ROLES.items()
    ]


def run_crew(task: str, roles: list[str] | None = None,
             model: str = "auto", process: str = "sequential") -> dict:
    """Convenience function to run a crew task."""
    crew = get_crew(model)
    return crew.run(task, roles=roles, process=process)
