from __future__ import annotations

import re
from typing import Any
from collections import OrderedDict
from openai import OpenAI
from core.config import CFG
from core.logger import log
from core.token_tracker import tracker as _tt

_MAX_USERS = 200  # Maximum distinct user histories to retain

# Qwen2.5 chat template markers
_IM_START = "<|im_start|>"
_IM_END = "<|im_end|>"


class AIChat:
    def __init__(self, model: str | None = None):
        self.model = model or CFG.TG_MODEL  # "deepseek" | "ollama" | "local" | "auto"
        self.context_rounds = CFG.CONTEXT_ROUNDS
        self.history: OrderedDict[str, list[dict[str, str]]] = OrderedDict()

        # Pre-init clients lazily — created on first use
        self._deepseek_client = None
        self._ollama_client = None

    # ----------------------------------------------------------------
    # Lazy client factories
    # ----------------------------------------------------------------
    def _get_deepseek_client(self) -> OpenAI:
        if self._deepseek_client is None:
            self._deepseek_client = OpenAI(
                api_key=CFG.DEEPSEEK_KEY, base_url=CFG.DEEPSEEK_URL
            )
        return self._deepseek_client

    def _get_ollama_client(self) -> OpenAI:
        if self._ollama_client is None:
            from core.model_router import get_ollama_url
            self._ollama_client = OpenAI(
                base_url=f"{get_ollama_url()}/v1", api_key="ollama"
            )
        return self._ollama_client

    # ----------------------------------------------------------------
    # Backend dispatch
    # ----------------------------------------------------------------
    def _resolve_backend(self, message: str) -> str:
        """Return 'deepseek', 'ollama', or 'local'."""
        if self.model == "auto":
            from core.model_router import route
            return route(message)
        return self.model

    def _call_backend(self, backend: str, messages: list[dict[str, str]]) -> str:
        if backend == "deepseek":
            return self._call_deepseek(messages)
        elif backend == "ollama":
            return self._call_ollama(messages)
        elif backend == "local":
            return self._call_local(messages)
        else:
            return f"[AI] 未知模型后端: {backend}"

    # ----------------------------------------------------------------
    # DeepSeek API
    # ----------------------------------------------------------------
    def _call_deepseek(self, messages: list[dict[str, str]]) -> str:
        client = self._get_deepseek_client()
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,  # type: ignore[arg-type]
            temperature=0.7,
            max_tokens=512,
        )
        usage = getattr(resp, "usage", None)
        if usage:
            _tt.record("deepseek", "telegram",
                        usage.prompt_tokens or 0,
                        usage.completion_tokens or 0)
        return resp.choices[0].message.content or ""

    # ----------------------------------------------------------------
    # Ollama API (OpenAI-compatible)
    # ----------------------------------------------------------------
    def _call_ollama(self, messages: list[dict[str, str]]) -> str:
        client = self._get_ollama_client()
        resp = client.chat.completions.create(
            model=CFG.OLLAMA_MODEL,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.7,
            max_tokens=512,
        )
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        if usage:
            _tt.record("ollama", "telegram",
                        usage.prompt_tokens or 0,
                        usage.completion_tokens or 0)
        # Strip Qwen3 <think>...</think> reasoning blocks
        return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()

    # ----------------------------------------------------------------
    # Local GGUF via llm_bridge
    # ----------------------------------------------------------------
    def _call_local(self, messages: list[dict[str, str]]) -> str:
        from core.llm_bridge import is_loaded, generate

        if not is_loaded():
            return "[AI] 本地模型未加载，请先启动服务器 (riycol run server) 或下载模型"

        # Build Qwen2.5 chat template prompt
        parts: list[str] = []
        for m in messages:
            parts.append(f"{_IM_START}{m['role']}\n{m['content']}{_IM_END}\n")
        parts.append(f"{_IM_START}assistant\n")
        prompt = "".join(parts)

        try:
            resp = generate(prompt, max_tokens=256, temperature=0.7)
            text = str(resp.get("choices", [{}])[0].get("text", "")).strip()
            from core.token_counter import count as _cnt
            _tt.record("local", "telegram", _cnt(prompt), _cnt(text))
            return text
        except Exception as e:
            raise Exception(f"Local model error: {e}")

    # ----------------------------------------------------------------
    # Main entry point
    # ----------------------------------------------------------------
    def get_reply(self, user_id: str, message: str) -> str:
        """获取AI回复，自动管理上下文和内存"""
        # 初始化或刷新用户历史（LRU）
        if user_id not in self.history:
            while len(self.history) >= _MAX_USERS:
                self.history.popitem(last=False)
            self.history[user_id] = []
        else:
            self.history.move_to_end(user_id)

        # 添加用户当前消息
        self.history[user_id].append({"role": "user", "content": message})

        # 构建上下文
        messages: list[dict[str, str]] = [
            {"role": "system", "content": (
                "你是 Riycol，一个本地部署的 AI 个人助手，运行在用户自己的 GPU 服务器上（Ollama + Qwen3 模型），"
                "无需联网即可工作。你可以通过工具访问本地文件、数据库和知识库。"
                "用中文回复，语气友好简洁。"
                "回复规则：1) 直接回应用户当前问题，不要编造无关内容；"
                "2) 简洁优先，用户问什么答什么；"
                "3) 只输出最终回复，不要模拟对话或自问自答；"
                "4) 简短问候用简短回复（一两句话即可）；"
                "5) 被问到身份时，说明你是本地私有化部署的 AI，不是云端服务。"
            )}
        ]
        recent = self.history[user_id][-2 * self.context_rounds:]
        messages.extend(recent)

        # 选择后端并调用
        backend = self._resolve_backend(message)
        log.info(f"TG AI backend={backend} msg={message[:40]}...")

        try:
            reply = self._call_backend(backend, messages)
        except Exception as e:
            log.error(f"TG AI error (backend={backend}): {e}")
            reply = f"[AI Error] {str(e)}"

        # Token 计数 (仅日志)
        from core.token_counter import count as count_tokens
        input_text = "".join(m["content"] for m in messages)
        log.info(f"TG AI tokens: in={count_tokens(input_text)} out={count_tokens(reply or '')}")

        # 添加AI回复到历史
        self.history[user_id].append({"role": "assistant", "content": reply or ""})

        # 裁剪历史（按轮次）
        max_len = 2 * self.context_rounds
        if len(self.history[user_id]) > max_len:
            self.history[user_id] = self.history[user_id][-max_len:]

        return reply or ""
