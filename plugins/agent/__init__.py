import sys, os, re, time, json
from typing import Any
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from core.plugin_loader import PluginInfo
from core.logger import log
from core.config import CFG
from core.memory_store import memory_store
from core.prompt_manager import prompts, build_messages, build_chatml
from core.retry import retry, CircuitOpenError
from core.token_tracker import tracker as _tracker

# ============================================================
# Agent 智能体系统
# ============================================================

class Agent:
    """单个智能体 (支持持久记忆)

    system_prompt can be:
      - A raw string (backward compat)
      - A (category, name) tuple referencing PromptLibrary, e.g. ("chat", "default")
      - None → defaults to ("chat", "default")
    """

    MAX_MEMORY = 14  # Keep at most 7 conversation rounds (14 messages)

    def __init__(self, name, role, model="auto", system_prompt=None):
        self.name = name
        self.role = role
        self.model = model
        self._prompt_ref: tuple[str, str] | None = None
        self._system_prompt_raw: str | None = None

        if isinstance(system_prompt, tuple) and len(system_prompt) == 2:
            self._prompt_ref = system_prompt
            self.system_prompt = self._get_system_prompt()
        elif isinstance(system_prompt, str) and system_prompt:
            self._system_prompt_raw = system_prompt
            self.system_prompt = system_prompt
        else:
            self._prompt_ref = ("chat", "default")
            self.system_prompt = self._get_system_prompt()

        self.memory: list[dict[str, str]] = []
        self._load_memory()

    def _get_system_prompt(self) -> str:
        """Resolve effective system prompt from library or raw string."""
        if self._system_prompt_raw:
            return self._system_prompt_raw
        cat, name = self._prompt_ref or ("chat", "default")
        try:
            return prompts.render(cat, name, agent_name=self.name, agent_role=self.role)
        except KeyError:
            log.warn(f"Prompt '{cat}/{name}' not found, using fallback")
            return f"你是{self.name}，负责{self.role}。请根据你的专业领域回答问题。"

    def _get_tool_prompt(self) -> str:
        """Resolve tool-use system prompt."""
        if self._system_prompt_raw:
            return self._system_prompt_raw
        try:
            return prompts.render("chat", "tool_use", agent_name=self.name, agent_role=self.role)
        except KeyError:
            return self._get_system_prompt()

    def _load_memory(self):
        """Restore conversation history from persistent store. Loads compacted summary if present."""
        try:
            saved = memory_store.get(self.name, "conversation_history", [])
            if saved:
                self.memory = saved[-self.MAX_MEMORY:]
                log.info(f"Agent '{self.name}': restored {len(self.memory)} messages")
            summary = self.load_context("conversation_summary", None)
            if summary and isinstance(summary, dict):
                summary_text = summary.get("text", "")
                if summary_text:
                    self.memory.insert(0, {"role": "system", "content": f"[历史摘要] {summary_text}"})
        except Exception as e:
            log.warn(f"Agent '{self.name}': memory load failed ({e})")

    def _save_memory(self):
        """Persist conversation history (only if changed). Strips error markers."""
        try:
            last = memory_store.get(self.name, "conversation_history", [])
            clean = [{k: v for k, v in m.items() if not k.startswith("_")} for m in self.memory]
            if last == clean:
                return
            memory_store.put(self.name, "conversation_history", clean)
        except Exception as e:
            log.warn(f"Agent '{self.name}': memory save failed ({e})")

    def save_context(self, key: str, value: Any):
        """Save arbitrary context data to persistent memory."""
        memory_store.put(self.name, key, value)

    def load_context(self, key: str, default: Any = None) -> Any:
        """Load context data from persistent memory."""
        return memory_store.get(self.name, key, default)

    @staticmethod
    def _strip_error_meta(msgs: list[dict[str, str]]) -> list[dict[str, str]]:
        """Remove internal meta keys (prefixed with _) before sending to LLM."""
        return [{k: v for k, v in m.items() if not k.startswith("_")} for m in msgs]

    @property
    def last_reply_was_error(self) -> bool:
        """Check if the most recent reply was an error."""
        if not self.memory:
            return False
        return bool(self.memory[-1].get("_error", False))

    @staticmethod
    def _check_safety(task: str) -> str | None:
        """Multi-layer safety filter: L1 pattern detection + threat prediction."""
        from core.security import security as sec

        # L1: Hard pattern check
        check = sec.check_dangerous_patterns(task)
        if not check.allowed:
            return f"[熔断 L1] 拒绝执行：{check.reason}。请提出安全的替代请求。"

        # Threat prediction
        threat = sec.predict_threat(task)
        if threat["threat_level"] in ("critical", "high"):
            signals = ", ".join(threat["signals"])
            return f"[预警] 检测到高危信号（{signals}），威胁等级={threat['threat_level']}。该操作已被阻止。"

        return None

    def _resolve_model(self, task: str) -> str:
        """Resolve 'auto' model to actual backend."""
        if self.model != "auto":
            return self.model
        from core.model_router import route
        return route(task)

    def compact_memory(self) -> str | None:
        """Summarize oldest messages when memory exceeds MAX_MEMORY.

        Keeps the 4 most recent messages intact, summarizes the rest via LLM,
        and stores the summary as a persistent context entry.
        Returns the summary text, or None if compaction was skipped.
        """
        if len(self.memory) <= self.MAX_MEMORY:
            return None
        keep = 4  # keep most recent 4 messages (2 turns)
        oldest = self.memory[:-keep] if len(self.memory) > keep else []
        if not oldest:
            return None
        # Convert oldest messages to text
        convo = "\n".join(
            f"[{m['role']}]: {m.get('content', '')[:300]}"
            for m in oldest if not m.get("_error")
        )
        if not convo.strip():
            return None
        try:
            summary_prompt = (
                "请用中文简要总结以下对话的关键信息、决定和上下文（200字以内）。\n\n" + convo
            )
            model = self._resolve_model("summarize memory")
            summary = raw_llm_call(model, self.system_prompt, summary_prompt, [], temperature=0.3, max_tokens=256)
            if summary:
                self.save_context("conversation_summary", {
                    "text": summary,
                    "ts": time.time(),
                    "messages_compacted": len(oldest),
                })
                self.memory = self.memory[-keep:]
                log.info(f"Agent '{self.name}': compacted {len(oldest)} messages → summary")
                return summary
        except Exception as e:
            log.warn(f"Agent '{self.name}': compaction failed ({e}), falling back to truncation")
            self.memory = self.memory[-self.MAX_MEMORY:]
        return None

    def act(self, task: str, context: str = "") -> str:
        """执行任务，自动记录对话历史并裁剪"""
        # Pre-model safety filter
        refusal = self._check_safety(task)
        if refusal:
            self.memory.append({"role": "user", "content": task})
            self.memory.append({"role": "assistant", "content": refusal})
            return refusal

        self.memory.append({"role": "user", "content": task})
        model = self._resolve_model(task)
        from core.model_router import record_backend_success, record_backend_failure
        try:
            if model == "deepseek":
                reply = self._call_deepseek(task, context)
            elif model == "ollama":
                reply = self._call_ollama(task, context)
            elif model == "local":
                reply = self._call_local(task, context)
            else:
                reply = f"[{self.name}] 模型 {model} 暂不支持"
            record_backend_success(model)
            self.memory.append({"role": "assistant", "content": reply})
        except CircuitOpenError:
            record_backend_failure(model)
            reply = f"[{self.name}] 模型服务暂时不可用，请稍后重试"
            self.memory.append({"role": "assistant", "content": reply, "_error": True})
        except Exception as e:
            record_backend_failure(model)
            log.error(f"Agent {self.name} error: {e}")
            reply = f"[{self.name}] 处理出错: {e}"
            self.memory.append({"role": "assistant", "content": reply, "_error": True})
        if len(self.memory) > self.MAX_MEMORY:
            self.compact_memory()
        self._save_memory()
        return reply

    @retry(max_attempts=3, base_delay=1.0, retryable=(ConnectionError, TimeoutError, OSError))
    def _call_deepseek(self, task: str, context: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=CFG.DEEPSEEK_KEY, base_url=CFG.DEEPSEEK_URL)
        extra = f"上下文信息:\n{context}" if context else ""
        messages = build_messages(
            system=self.system_prompt,
            user_msg=task,
            history=self._strip_error_meta(self.memory[-7:-1]),
            extra_context=extra,
        )
        resp = client.chat.completions.create(
            model="deepseek-chat", messages=messages, temperature=0.7  # type: ignore[arg-type]
        )
        usage = getattr(resp, "usage", None)
        if usage:
            _tracker.record("deepseek", "agent",
                            usage.prompt_tokens or 0,
                            usage.completion_tokens or 0)
        return resp.choices[0].message.content or ""

    @retry(max_attempts=3, base_delay=1.0, retryable=(ConnectionError, TimeoutError, OSError))
    def _call_ollama(self, task: str, context: str) -> str:
        """Use Ollama API (OpenAI-compatible)."""
        from core.model_router import get_ollama_url
        from openai import OpenAI
        client = OpenAI(base_url=f"{get_ollama_url()}/v1", api_key="ollama")
        extra = f"上下文:\n{context}" if context else ""
        messages = build_messages(
            system=self.system_prompt,
            user_msg=task,
            history=self._strip_error_meta(self.memory[-7:-1]),
            extra_context=extra,
        )
        model = CFG.OLLAMA_MODEL
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=0.7)  # type: ignore[arg-type]
        usage = getattr(resp, "usage", None)
        if usage:
            _tracker.record("ollama", "agent",
                            usage.prompt_tokens or 0,
                            usage.completion_tokens or 0)
        return resp.choices[0].message.content or ""

    def _call_local(self, task: str, context: str) -> str:
        """Use local model via LLM bridge."""
        from core.llm_bridge import is_loaded, generate
        if not is_loaded():
            return f"[{self.name}] 本地模型未加载"
        try:
            extra = f"上下文:\n{context}" if context else ""
            prompt = build_chatml(
                system=self.system_prompt,
                user_msg=task,
                history=self._strip_error_meta(self.memory[-7:-1]),
                extra_context=extra,
            )
            resp = generate(prompt, max_tokens=512, temperature=0.7)
            text = str(resp.get("choices", [{}])[0].get("text", "")).strip()
            from core.token_counter import count as _cnt
            _tracker.record("local", "agent",
                            _cnt(prompt), _cnt(text))
            return text
        except Exception as e:
            raise Exception(f"Local model error: {e}")

    def act_with_react(self, task: str, context: str = "", max_rounds: int = 5) -> str:
        """Execute a task using the ReAct paradigm: Thought → Action → Observation → Final Answer.

        Works with ALL model backends (not just DeepSeek function calling).
        The model is prompted to think step-by-step, decide which tool to call,
        observe the result, and iterate until it produces a final answer.
        """
        refusal = self._check_safety(task)
        if refusal:
            self.memory.append({"role": "user", "content": task})
            self.memory.append({"role": "assistant", "content": refusal})
            return refusal

        from core.tools import tool_registry

        tool_list = "\n".join(
            f"- {t.name_for_model}: {t.description}"
            for t in tool_registry._tools.values()
        )
        react_system = f"""{self._get_system_prompt()}

## Available Tools
{tool_list}

## ReAct Protocol
Follow this cycle step by step:

**Step 1 - Thought**: What do I need? What have I observed? Can I answer now?
**Step 2 - Action** (if needed): Call a tool. Write clean JSON arguments on ONE line, no markdown fences.

TOOL_CALL: <tool_name>
ARGUMENTS: {{"key": "value"}}

**Step 3 - Observation**: Read the tool result carefully.
**Step 4 - Final Answer**: When ready, output:

FINAL_ANSWER:
Your complete answer here.

## Rules
- Max {max_rounds} tool calls total, then you MUST answer.
- ONE tool per step. Write JSON args on a single line: ARGUMENTS: {{"file_path": "README.md"}}
- Never wrap args in ``` or ''' — pure JSON only.
- If tool fails, try alternative approach or give best answer.
- For simple questions (greeting, math, knowledge), answer directly — no tools needed."""

        self.memory.append({"role": "user", "content": task})
        history = list(self.memory[-7:-1]) if len(self.memory) > 1 else []

        model = self._resolve_model(task)
        prompt_context = context

        for round_num in range(max_rounds):
            # Build prompt with tool results from previous rounds
            user_prompt = task
            if prompt_context:
                user_prompt = f"Task: {task}\n\nObservations so far:\n{prompt_context}"
            if round_num > 0:
                user_prompt += f"\n\nContinue with the ReAct cycle. You have {max_rounds - round_num} tool calls remaining."

            try:
                reply = self._raw_call(model, react_system, user_prompt, history)
            except Exception as e:
                log.error(f"ReAct step {round_num} failed: {e}")
                prompt_context += f"\n[Step {round_num + 1}] Error: {e}"
                continue

            # Parse the response
            if "FINAL_ANSWER:" in reply:
                # Extract everything after FINAL_ANSWER:
                final = reply.split("FINAL_ANSWER:", 1)[1].strip()
                self.memory.append({"role": "assistant", "content": final})
                if len(self.memory) > self.MAX_MEMORY:
                    self.compact_memory()
                self._save_memory()
                return final

            # Parse TOOL_CALL
            if "TOOL_CALL:" in reply:
                tc_match = reply.split("TOOL_CALL:", 1)[1].strip()
                arg_match = ""
                if "ARGUMENTS:" in tc_match:
                    tc_name, arg_part = tc_match.split("ARGUMENTS:", 1)
                    tc_name = tc_name.strip()
                    arg_match = arg_part.strip()
                else:
                    tc_name = tc_match.split("\n")[0].strip()

                tool = tool_registry.get(tc_name)
                if not tool:
                    prompt_context += f"\n[Step {round_num + 1}] Unknown tool: {tc_name}. Available: {', '.join(tool_registry.list_names())}"
                    continue

                # Clean arg string: strip markdown, handle common LLM format mistakes
                clean_args = arg_match.strip().strip("`").strip()
                # Strip trailing markdown fence
                if clean_args.endswith("```"):
                    clean_args = clean_args[:-3].strip()
                # Unwrap Python-style dict: {'input': '...'} → just the inner JSON
                py_match = re.match(r"^\{'input':\s*'(.+)'\}$", clean_args, re.DOTALL)
                if py_match:
                    clean_args = py_match.group(1).strip()
                try:
                    args = json.loads(clean_args) if clean_args else {}
                except json.JSONDecodeError:
                    # Fallback: pass entire string as input, truncated
                    args = {"input": arg_match.strip()[:2000]}

                log.info(f"ReAct [{round_num + 1}]: Thought→Action={tc_name}({str(args)[:60]})")
                result = tool.execute(args)
                observation = result[:2000]  # Truncate long observations
                prompt_context += f"\n[Step {round_num + 1}] TOOL={tc_name} | RESULT: {observation}"
                continue

            # No tool call and no final answer — treat as final
            self.memory.append({"role": "assistant", "content": reply})
            if len(self.memory) > self.MAX_MEMORY:
                self.compact_memory()
            self._save_memory()
            return reply

        # Max rounds exhausted — force final synthesis
        fallback_prompt = f"{task}\n\nBased on the observations above, please provide your best answer now. Start with FINAL_ANSWER:"
        try:
            final = self._raw_call(model, react_system, fallback_prompt, history)
            if "FINAL_ANSWER:" in final:
                final = final.split("FINAL_ANSWER:", 1)[1].strip()
        except Exception:
            final = "ReAct cycle incomplete. Please try again with a simpler task."
        self.memory.append({"role": "assistant", "content": final})
        if len(self.memory) > self.MAX_MEMORY:
            self.compact_memory()
        self._save_memory()
        return final

    def act_with_reflection(self, task: str, context: str = "",
                            max_refine_rounds: int = 2) -> str:
        """Execute task with reflection loop: Act → Critique → Refine → Repeat.

        1. Execute initial answer via act()
        2. Self-critique against the task
        3. If issues found, refine and re-evaluate up to max_refine_rounds
        """
        from core.reflection import Reflection

        initial = self.act(task, context)
        if not initial or initial.startswith("["):
            return initial  # don't reflect on errors

        reflection = Reflection(model=self._resolve_model(task), max_refine_rounds=max_refine_rounds)

        def _refine_fn(refine_prompt: str) -> str:
            return self.act(refine_prompt, context)

        return reflection.reflect_and_refine(task, initial, _refine_fn, max_refine_rounds)

    # ---- streaming ----

    def act_stream(self, task: str, context: str = ""):
        """Stream tokens one at a time via generator. deepseek/ollama only; local falls back."""
        self.memory.append({"role": "user", "content": task})
        model = self._resolve_model(task)
        try:
            if model == "deepseek":
                yield from self._call_deepseek_stream(task, context)
            elif model == "ollama":
                yield from self._call_ollama_stream(task, context)
            else:
                yield self.act(task, context)
        except CircuitOpenError:
            yield f"[{self.name}] 模型服务暂时不可用"
        except Exception as e:
            log.error(f"Agent {self.name} stream error: {e}")
            yield f"[{self.name}] 处理出错: {e}"

    def _call_deepseek_stream(self, task: str, context: str):
        from openai import OpenAI
        client = OpenAI(api_key=CFG.DEEPSEEK_KEY, base_url=CFG.DEEPSEEK_URL)
        extra = f"上下文:\n{context}" if context else ""
        msgs = build_messages(system=self.system_prompt, user_msg=task,
            history=self._strip_error_meta(self.memory[-7:-1]), extra_context=extra)
        full = []
        prompt_tokens = 0
        completion_tokens = 0
        for chunk in client.chat.completions.create(
            model="deepseek-chat", messages=msgs, temperature=0.7,
            stream=True, stream_options={"include_usage": True}):  # type: ignore[arg-type]
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full.append(token)
                yield token
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0
        if prompt_tokens or completion_tokens:
            _tracker.record("deepseek", "agent", prompt_tokens, completion_tokens)
        self.memory.append({"role": "assistant", "content": "".join(full)})
        self._save_memory()

    def _call_ollama_stream(self, task: str, context: str):
        from core.model_router import get_ollama_url
        from openai import OpenAI
        client = OpenAI(base_url=f"{get_ollama_url()}/v1", api_key="ollama")
        extra = f"上下文:\n{context}" if context else ""
        msgs = build_messages(system=self.system_prompt, user_msg=task,
            history=self._strip_error_meta(self.memory[-7:-1]), extra_context=extra)
        full = []
        prompt_tokens = 0
        completion_tokens = 0
        for chunk in client.chat.completions.create(
            model=CFG.OLLAMA_MODEL, messages=msgs, temperature=0.7,
            stream=True, stream_options={"include_usage": True}):  # type: ignore[arg-type]
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full.append(token)
                yield token
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0
        if prompt_tokens or completion_tokens:
            _tracker.record("ollama", "agent", prompt_tokens, completion_tokens)
        self.memory.append({"role": "assistant", "content": "".join(full)})
        self._save_memory()

    def act_with_plan(self, task: str, context: str = "", max_rounds: int = 5,
                      reflect: bool = False) -> str:
        """Execute task with Planning before ReAct: Plan → Execute → Synthesize → (optional) Reflect.

        1. PLAN: Decompose task into structured steps via Planner
        2. EXECUTE: Run each step, using ReAct for tool-required steps, act() for reasoning
        3. SYNTHESIZE: Merge per-step results into final answer
        4. (optional) REFLECT: Self-critique and refine
        """
        from core.planner import Planner
        from core.tools import tool_registry

        log.info(f"[Plan] Agent '{self.name}' planning: {task[:60]}...")
        planner = Planner(model=self._resolve_model(task))
        plan = planner.plan(task, context=context, available_tools=tool_registry.list_names())
        log.info(f"[Plan] {len(plan.steps)} steps")

        self.memory.append({"role": "system", "content": f"[PLAN] {len(plan.steps)} steps for: {task[:100]}"})

        results: dict[int, str] = {}
        for step in plan.steps:
            step_task = f"[Step {step.index}/{len(plan.steps)}] {step.description}"
            if step.tool and step.tool_args:
                result = self.act_with_react(step_task, context=context, max_rounds=min(3, max_rounds))
            else:
                result = self.act(step_task, context=context)
            results[step.index] = result
            self.memory.append({"role": "system", "content": f"[STEP {step.index}] {result[:500]}"})

        # Synthesize
        final = self._synthesize_plan_results(task, plan, results)

        if reflect:
            final = self.act_with_reflection(task, max_refine_rounds=1)

        self.memory.append({"role": "assistant", "content": final})
        if len(self.memory) > self.MAX_MEMORY:
            self.compact_memory()
        self._save_memory()
        return final

    def _synthesize_plan_results(self, task: str, plan, results: dict[int, str]) -> str:
        """Synthesize per-step results into a coherent final answer."""
        parts = "\n\n".join(
            f"## Step {i}\n{results.get(i, 'N/A')[:1500]}"
            for i in sorted(results.keys())
        )
        synth_prompt = f"原始任务: {task}\n\n各步骤产出:\n{parts}\n\n请综合以上结果，给出一份完整、条理清晰的最终回答。"
        return self.act(synth_prompt)

    def _raw_call(self, model: str, system: str, user: str, history: list) -> str:
        """Thin wrapper for backward compat. Delegates to module-level raw_llm_call."""
        return raw_llm_call(model, system, user, history)

    def act_with_tools(self, task: str, context: str = "", max_tool_rounds: int = 3) -> str:
        """Execute a task with tool-use capability (DeepSeek function calling)."""
        if self.model != "deepseek":
            return self.act(task, context)

        from core.tools import get_openai_tools, tool_registry
        from openai import OpenAI

        self.memory.append({"role": "user", "content": task})
        client = OpenAI(api_key=CFG.DEEPSEEK_KEY, base_url=CFG.DEEPSEEK_URL)
        extra = f"上下文:\n{context}" if context else ""
        messages: list[dict[str, Any]] = build_messages(
            system=self._get_tool_prompt(),
            user_msg=task,
            history=self._strip_error_meta(self.memory[-7:-1]),
            extra_context=extra,
        )

        for round_num in range(max_tool_rounds):
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,  # type: ignore[arg-type]
                tools=get_openai_tools(),  # type: ignore[arg-type]
                temperature=0.3,
            )
            choice = resp.choices[0]
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    fn = getattr(tc, "function", None)
                    if fn is None:
                        continue
                    tool = tool_registry.get(fn.name)
                    if not tool:
                        result = json.dumps({"error": f"Unknown tool: {fn.name}"})
                    else:
                        args = json.loads(fn.arguments)
                        log.info(f"Tool '{fn.name}' called by '{self.name}': {str(args)[:80]}")
                        result = tool.execute(args)
                    messages.append({"role": "assistant", "tool_calls": [tc.model_dump()]})
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            else:
                reply = choice.message.content or ""
                self.memory.append({"role": "assistant", "content": reply})
                if len(self.memory) > self.MAX_MEMORY:
                    self.compact_memory()
                self._save_memory()
                return reply

        # Max rounds exceeded — generate final response
        messages.append({"role": "user", "content": "请基于以上工具调用结果给出最终回答。"})
        resp = client.chat.completions.create(
            model="deepseek-chat", messages=messages, temperature=0.7)  # type: ignore[arg-type]
        reply = resp.choices[0].message.content or ""
        self.memory.append({"role": "assistant", "content": reply})
        if len(self.memory) > self.MAX_MEMORY:
            self.compact_memory()
        self._save_memory()
        return reply


# ============================================================
# Module-level shared LLM call (used by Agent, Planner, Reflection)
# ============================================================

@retry(max_attempts=3, base_delay=1.0, retryable=(ConnectionError, TimeoutError, OSError))
def raw_llm_call(model: str, system: str, user: str, history: list | None = None,
                 temperature: float = 0.3, max_tokens: int = 1024) -> str:
    """Single-turn raw call to any model backend. Returns text response."""
    hist = history or []
    if model == "deepseek":
        from openai import OpenAI
        client = OpenAI(api_key=CFG.DEEPSEEK_KEY, base_url=CFG.DEEPSEEK_URL)
        msgs = [{"role": "system", "content": system}] + hist + [{"role": "user", "content": user}]
        resp = client.chat.completions.create(
            model="deepseek-chat", messages=msgs, temperature=temperature)  # type: ignore[arg-type]
        usage = getattr(resp, "usage", None)
        if usage:
            _tracker.record("deepseek", "agent",
                            usage.prompt_tokens or 0,
                            usage.completion_tokens or 0)
        return resp.choices[0].message.content or ""
    elif model == "ollama":
        from core.model_router import get_ollama_url
        from openai import OpenAI
        client = OpenAI(base_url=f"{get_ollama_url()}/v1", api_key="ollama")
        msgs = [{"role": "system", "content": system}] + hist + [{"role": "user", "content": user}]
        resp = client.chat.completions.create(
            model=CFG.OLLAMA_MODEL, messages=msgs, temperature=temperature)  # type: ignore[arg-type]
        usage = getattr(resp, "usage", None)
        if usage:
            _tracker.record("ollama", "agent",
                            usage.prompt_tokens or 0,
                            usage.completion_tokens or 0)
        return resp.choices[0].message.content or ""
    else:
        from core.llm_bridge import is_loaded, generate
        if not is_loaded():
            raise RuntimeError("Local model not loaded")
        parts = [f"<|im_start|>system\n{system}<|im_end|>\n"]
        for m in hist:
            parts.append(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n")
        parts.append(f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n")
        prompt = "".join(parts)
        resp = generate(prompt, max_tokens=max_tokens, temperature=temperature)
        text = str(resp.get("choices", [{}])[0].get("text", "")).strip()
        from core.token_counter import count as _cnt
        _tracker.record("local", "agent", _cnt(prompt), _cnt(text))
        return text


class AgentSwarm:
    """Multi-agent swarm with task dispatching, parallel execution, and synthesis.

    Core 'Riycol' agent handles general tasks. Specialized agents (reviewer, researcher,
    writer, coder) are initialized from crew_agent CREW_ROLES for multi-agent delegation.
    """

    def __init__(self):
        self.agents: dict[str, Agent] = {}
        # Core generalist agent
        self.agents["Riycol"] = Agent(
            "Riycol", "全能AI助手——分析、研究、写作、审查、记忆",
            system_prompt=("chat", "default"),
        )
        # Specialized agents (lazy init references, actual agents created on demand)
        self._specialized: dict[str, Agent] = {}
        self._init_specialized()

    def _init_specialized(self):
        """Initialize specialized agents from crew_agent CREW_ROLES."""
        try:
            from plugins.agent.crew_agent import CREW_ROLES
            for name, (role, backstory) in CREW_ROLES.items():
                if name == "riycol":
                    continue
                self._specialized[name] = Agent(
                    name=f"Riycol-{name.title()}",
                    role=role,
                    system_prompt=backstory,
                )
        except ImportError:
            pass  # crew_agent not installed
        except Exception as e:
            log.warn(f"Swarm: failed to init specialized agents: {e}")

    def add_agent(self, agent: Agent):
        self.agents[agent.name] = agent

    def _get_agent(self, role: str) -> Agent | None:
        if role == "riycol":
            return self.agents.get("Riycol")
        return self._specialized.get(role)

    def _safe_act(self, name: str, task: str, context: str = "") -> str:
        agent = self.agents.get(name) or self._specialized.get(name)
        if not agent:
            return ""
        try:
            return agent.act(task, context)
        except Exception as e:
            log.error(f"[Swarm] Agent '{name}' failed: {e}")
            return ""

    def run(self, task: str, parallel: bool = True) -> str:
        """Dispatch task to appropriate agents and synthesize results.

        For simple tasks, uses Riycol directly. For complex tasks, decomposes
        and distributes to specialized agents in parallel or sequentially.
        """
        log.info(f"[Swarm] Task: {task[:60]}...")
        roles = self._resolve_roles(task)

        if len(roles) <= 1:
            result = self._safe_act("Riycol", task)
            return result or f"[Swarm] 无法处理: {task[:50]}..."

        # Multi-agent: decompose and dispatch
        subtasks = self._decompose_for_roles(task, roles)
        if parallel:
            results = self._run_parallel(subtasks)
        else:
            results = self._run_sequential(subtasks)

        return self._synthesize(task, results)

    def run_with_review(self, task: str, memory_context: str = "") -> str:
        """Process task with self-review via Reflection module."""
        context = f"历史相关记忆:\n{memory_context}" if memory_context else ""
        result = self._safe_act("Riycol", task, context=context)
        if not result:
            return f"[Swarm] 无法处理: {task[:50]}..."

        from core.reflection import Reflection
        reflection = Reflection(model=self.agents["Riycol"]._resolve_model(task), max_refine_rounds=2)
        refined = reflection.reflect_and_refine(
            task, result,
            execute_fn=lambda t: self._safe_act("Riycol", t),
            max_rounds=2,
        )
        return refined or result

    def simple_run(self, task: str) -> str:
        """Simple single-agent mode."""
        if CFG.DEEPSEEK_KEY:
            return self.agents["Riycol"].act(task)
        return "[Swarm] 未配置API密钥"

    # ---- multi-agent internals ----

    def _resolve_roles(self, task: str) -> list[str]:
        """Determine which agents are needed. Returns ['riycol'] for simple tasks."""
        if len(task) < 100 and task.count("\n") < 3:
            return ["riycol"]
        roles = {"riycol"}
        tl = task.lower()
        if any(kw in tl for kw in ("代码", "code", "debug", "实现", "function", "函数", "bug")):
            roles.add("coder")
        if any(kw in tl for kw in ("调研", "研究", "分析", "对比", "评估", "research")):
            roles.add("researcher")
        if any(kw in tl for kw in ("写", "文案", "文章", "报告", "文档", "write", "总结")):
            roles.add("writer")
        if len(roles) > 1:
            roles.add("reviewer")
        return list(roles)

    def _decompose_for_roles(self, task: str, roles: list[str]) -> list[dict]:
        """Create one subtask per role."""
        return [{"role": r, "description": task} for r in roles if r != "reviewer"]

    def _run_parallel(self, subtasks: list[dict]) -> dict[str, str]:
        """Execute subtasks in parallel using ThreadPoolExecutor."""
        import concurrent.futures
        results: dict[str, str] = {}

        def _exec(st):
            role = st["role"]
            agent = self._get_agent(role)
            if agent is None:
                return role, f"[{role}] Agent not available"
            try:
                return role, agent.act(st["description"])
            except Exception as e:
                log.error(f"[Swarm] {role} failed: {e}")
                return role, f"[{role}] Error: {e}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(_exec, st): st for st in subtasks}
            for future in concurrent.futures.as_completed(futures):
                role, result = future.result()
                results[role] = result
        return results

    def _run_sequential(self, subtasks: list[dict]) -> dict[str, str]:
        """Execute subtasks sequentially, passing results as context."""
        results: dict[str, str] = {}
        ctx: list[str] = []
        for st in subtasks:
            role = st["role"]
            task = st["description"]
            if ctx:
                task += "\n\n参考前序结果:\n" + "\n".join(ctx[-2:])
            agent = self._get_agent(role)
            result = self._safe_act(agent.name if agent else "Riycol", task) if agent else ""
            results[role] = result
            ctx.append(f"[{role}]: {result[:300]}")
        return results

    def _synthesize(self, task: str, results: dict[str, str]) -> str:
        """Merge multi-agent results into final answer."""
        parts = "\n\n".join(
            f"## {role}\n{output[:1500]}"
            for role, output in results.items()
        )
        synth_prompt = f"原始任务: {task}\n\n各角色产出:\n{parts}\n\n请综合以上产出，给出一份完整的最终回答。"
        return self._safe_act("Riycol", synth_prompt)

    # ---- autonomous tasks ----

    def auto_daily_summary(self):
        """Generate daily conversation summary."""
        try:
            from core.db import DB
            rows = DB.conn.execute(
                "SELECT role, content FROM conversations "
                "WHERE created_at > ? ORDER BY id DESC LIMIT 40",
                (time.time() - 86400,)
            ).fetchall()
            if not rows:
                return
            convo_text = "\n".join(f"[{r['role']}]: {r['content'][:200]}" for r in rows)
            summary = self.run(f"请用中文简要总结以下对话的关键主题和要点（200字以内）:\n\n{convo_text}")
            date_str = time.strftime("%Y%m%d")
            memory_store.put("swarm", "daily_summary_" + date_str, {
                "date": time.strftime("%Y-%m-%d"), "summary": summary,
                "conversation_count": len(rows),
            }, ttl=30 * 86400)
            log.info(f"[Auto] Daily summary saved ({len(rows)} messages)")
            from core.sync_notion import log_to_notion
            log_to_notion(f"日报-{date_str}", summary, tags=["日报", "summary"])
        except Exception as e:
            log.error(f"[Auto] Daily summary failed: {e}")

    def auto_kb_health_check(self):
        """Check knowledge base health."""
        try:
            from plugins.server.kb import KnowledgeBase
            from core.config import CFG as C
            kb = KnowledgeBase(docs_dir=str(C.DOCS))
            stats = kb.stats()
            memory_store.put("swarm", "kb_health", {
                "checked_at": time.time(),
                "documents": stats.get("documents", 0),
                "engine": stats.get("engine", "unknown"),
            }, ttl=7200)
        except Exception as e:
            log.error(f"[Auto] KB health check failed: {e}")

    def auto_memory_cleanup(self):
        """Clean up expired memory entries."""
        try:
            removed = memory_store.gc()
            if removed:
                log.info(f"[Auto] Memory cleanup: removed {removed} expired entries")
        except Exception as e:
            log.error(f"[Auto] Memory cleanup failed: {e}")

    def auto_notion_sync(self):
        """Sync local knowledge base with Notion (pull then push)."""
        try:
            from core.sync_notion import pull, push
            pulled = pull()
            pushed = push()
            status = "ok" if (pulled or pushed) else "no_changes"
            memory_store.put("swarm", "notion_sync", {
                "synced_at": time.time(),
                "pulled": pulled,
                "pushed": pushed,
                "status": status,
            }, ttl=86400)
            if pulled or pushed:
                log.info(f"[Auto] Notion sync: pulled={pulled} pushed={pushed}")
        except Exception as e:
            log.error(f"[Auto] Notion sync failed: {e}")

    @staticmethod
    def register_scheduled_tasks(sched):
        """Register autonomous tasks with the scheduler."""
        swarm = AgentSwarm()
        sched.add("daily_summary", swarm.auto_daily_summary, daily_at="08:00")
        sched.add("kb_health", swarm.auto_kb_health_check, every_seconds=3600)
        sched.add("memory_cleanup", swarm.auto_memory_cleanup, daily_at="03:00")
        sched.add("notion_sync", swarm.auto_notion_sync, every_seconds=1800)
        log.info("[Auto] Registered 4 autonomous tasks")


# ============================================================
# 插件入口
# ============================================================

_swarm = None

def register():
    return PluginInfo(name='agent', version='2.0', description='Agent swarm system - Multi-agent collaboration')

def start():
    global _swarm
    _swarm = AgentSwarm()
    log.info(f'agent: swarm started with {len(_swarm.agents)} agents')

def stop():
    global _swarm
    _swarm = None
    log.info('agent: swarm stopped')

def get_swarm():
    """获取智能体实例（供其他模块使用）"""
    global _swarm
    return _swarm
