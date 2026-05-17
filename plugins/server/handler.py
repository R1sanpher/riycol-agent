"""
handler.py — Qwen2.5 统一推理服务
==================================
HTTP API 服务: 流式输出 + 聊天历史 + 知识库(可选)

环境变量控制:
    USE_KB=0    禁用知识库 (默认启用)
    PORT=8000   修改端口 (默认8000)
    DEBUG=1     显示详细日志
"""

import time, sys, json, hmac, threading, datetime
from collections import OrderedDict
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
from typing import Any

# ============================================================
# 配置
# ============================================================
from core.config import CFG
from core.prompt_manager import prompts as _pm
from core.token_tracker import tracker

DEBUG = CFG.DEBUG

# 可选加载知识库
kb = None
_kb_thread = None
if CFG.USE_KB:
    try:
        from plugins.server.kb import KnowledgeBase
        CFG.DOCS.mkdir(parents=True, exist_ok=True)
        kb = KnowledgeBase(docs_dir=str(CFG.DOCS))
        kb.watch(interval=30)  # Initial full scan

        # 后台定期增量扫描
        import threading as _threading
        _kb_ref = kb  # capture for type narrowing
        def _kb_watch_loop():
            import time as _time
            while True:
                _time.sleep(30)
                if _kb_ref is None:
                    break
                try:
                    _kb_ref._scan(incremental=True)
                    if _kb_ref._vector_kb:
                        _kb_ref._vector_kb.watch()
                except Exception as _se:
                    if DEBUG: print(f"  [KB] incremental scan error: {_se}")
        _kb_thread = _threading.Thread(target=_kb_watch_loop, daemon=True)
        _kb_thread.start()
    except Exception as e:
        if DEBUG: print(f"  [KB] 加载失败: {e}")

# ============================================================
# 限流器
# ============================================================

class RateLimiter:
    """Sliding-window rate limiter per client IP."""
    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._clients: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            if client_ip not in self._clients:
                self._clients[client_ip] = []
            self._clients[client_ip] = [t for t in self._clients[client_ip] if t > cutoff]
            if len(self._clients[client_ip]) >= self.max_requests:
                return False
            self._clients[client_ip].append(now)
            return True

    def cleanup(self):
        """Drop expired entries to limit memory growth."""
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            for ip in list(self._clients.keys()):
                self._clients[ip] = [t for t in self._clients[ip] if t > cutoff]
                if not self._clients[ip]:
                    del self._clients[ip]

rate_limiter = RateLimiter()

# ============================================================
# 聊天并发队列 — 防止 Ollama 多请求 OOM
# ============================================================

class ChatQueue:
    """Semaphore-based concurrency guard for local model inference."""

    def __init__(self, max_concurrent: int = 2):
        self._sem = threading.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.active = 0
        self.waiting = 0
        self.total_processed = 0
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 120) -> bool:
        with self._lock:
            self.waiting += 1
        ok = self._sem.acquire(timeout=timeout)
        with self._lock:
            self.waiting -= 1
            if ok:
                self.active += 1
        return ok

    def release(self):
        with self._lock:
            self.active -= 1
            self.total_processed += 1
        self._sem.release()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "max_concurrent": self.max_concurrent,
                "active": self.active,
                "waiting": self.waiting,
                "total_processed": self.total_processed,
            }


chat_queue = ChatQueue(max_concurrent=2)

# ============================================================
# 指标收集
# ============================================================

class Metrics:
    """In-memory metrics with latency tracking and token counting."""

    def __init__(self):
        self.requests_total = 0
        self.errors_total = 0
        self.timeout_errors = 0
        self.chat_requests = 0
        self.stream_requests = 0
        self.start_time = time.time()
        # Latency tracking (ring buffer, last 200 requests)
        self._latencies: list[float] = []
        self._max_latency_samples = 200
        # Token tracking
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        # Lock for thread safety
        self._lock = threading.Lock()

    def record_latency(self, seconds: float):
        with self._lock:
            self._latencies.append(seconds)
            if len(self._latencies) > self._max_latency_samples:
                self._latencies = self._latencies[-self._max_latency_samples:]

    def record_tokens(self, prompt_tokens: int, completion_tokens: int):
        with self._lock:
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens

    def _percentile(self, pct: float) -> float:
        if not self._latencies:
            return 0.0
        sorted_lat = sorted(self._latencies)
        idx = int(len(sorted_lat) * pct / 100)
        idx = min(idx, len(sorted_lat) - 1)
        return round(sorted_lat[idx], 3)

    def snapshot(self) -> dict[str, Any]:
        uptime = int(time.time() - self.start_time)
        with self._lock:
            latencies = list(self._latencies)
        return {
            "uptime_seconds": uptime,
            "requests_total": self.requests_total,
            "errors_total": self.errors_total,
            "timeout_errors": self.timeout_errors,
            "error_rate": round(self.errors_total / max(self.requests_total, 1), 4),
            "chat_requests": self.chat_requests,
            "stream_requests": self.stream_requests,
            "active_sessions": len(chat_history),
            "chat_queue": chat_queue.snapshot(),
            "latency": {
                "p50": self._percentile(50),
                "p90": self._percentile(90),
                "p99": self._percentile(99),
                "avg": round(sum(latencies) / max(len(latencies), 1), 3),
                "samples": len(latencies),
            },
            "tokens": {
                "total_prompt": self.total_prompt_tokens,
                "total_completion": self.total_completion_tokens,
            },
        }

metrics = Metrics()

# ============================================================
# API Key 鉴权
# ============================================================

def check_auth(handler) -> bool:
    """Verify API key if configured. Returns True if auth passes or not required."""
    if not CFG.API_KEY:
        return True
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return hmac.compare_digest(token, CFG.API_KEY)
    return False

# ============================================================
# HTTP处理器
# ============================================================

# 数据库（自动记录对话，为蒸馏做准备）
db = None
if CFG.USE_DB:
    try:
        from core.db import Database
        db = Database()
        if DEBUG: print(f"  [DB] 数据库就绪: {CFG.DB_PATH}")
    except Exception as e:
        if DEBUG: print(f"  [DB] 加载失败: {e}")

llm: Any = None

# 使用 OrderedDict 实现 LRU 上限，防止内存泄漏
chat_history: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
chat_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")

        if path == "/ping":
            return self._json({"pong": True, "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()})

        metrics.requests_total += 1

        # WebSocket upgrade
        if path == "/ws":
            try:
                from plugins.server.ws_handler import handle_ws_upgrade, ws_chat_loop
                if handle_ws_upgrade(self):
                    ws_chat_loop(self)
                    return
            except Exception as e:
                if DEBUG: print(f"  [WS] Upgrade failed: {e}")

        if not path or path == "/":
            return self._serve_file("index.html")
        elif path == "/health":
            return self._health_check()
        elif path == "/metrics":
            if not check_auth(self):
                return self._json({"error": "Unauthorized"}, 401)
            return self._json(metrics.snapshot())
        elif path == "/api/tokens":
            return self._json(tracker.snapshot(limit=200))
        elif path == "/tokens":
            return self._serve_file("tokens.html")
        elif path == "/scheduler":
            if not check_auth(self):
                return self._json({"error": "Unauthorized"}, 401)
            from core.scheduler import scheduler as sched
            return self._json(sched.snapshot())
        elif path == "/memory":
            if not check_auth(self):
                return self._json({"error": "Unauthorized"}, 401)
            from core.memory_store import memory_store as mem
            return self._json(mem.stats())
        elif path == "/kb/status":
            return self._kb_status()
        elif path == "/db/stats":
            if not check_auth(self):
                return self._json({"error": "Unauthorized"}, 401)
            return self._db_stats()
        elif path == "/prompts":
            if not check_auth(self):
                return self._json({"error": "Unauthorized"}, 401)
            return self._prompts_get()
        elif path == "/clear":
            return self._clear_history()
        elif path == "/skills":
            return self._skills_get()
        else:
            self.send_error(404)

    def _health_check(self):
        """Health check with dependency status."""
        status = "ok"
        checks: dict[str, Any] = {"model": llm is not None}

        if db:
            try:
                db.stats()
                checks["db"] = True
            except Exception as e:
                checks["db"] = str(e)
                status = "degraded"
        else:
            checks["db"] = "disabled"

        if kb:
            try:
                kb_stats = kb.stats() if hasattr(kb, 'stats') else {}
                checks["kb"] = {"enabled": True, "documents": kb_stats.get("documents", 0)}
            except Exception as e:
                checks["kb"] = str(e)
                status = "degraded"
        else:
            checks["kb"] = "disabled"

        if not llm:
            status = "unavailable"

        self._json({"status": status, "checks": checks})

    def _kb_status(self):
        if not kb:
            return self._json({"enabled": False})
        try:
            stats = kb.stats() if hasattr(kb, 'stats') else {}
            self._json({
                "enabled": True,
                "engine": kb.engine_name,
                "documents": stats.get("documents", 0),
                "mode": kb.mode,
            })
        except Exception as e:
            self._json({"enabled": True, "error": str(e)})

    def _db_stats(self):
        if not db:
            return self._json({"enabled": False})
        try:
            stats = db.stats()
            self._json({"enabled": True, **stats})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _prompts_get(self):
        """GET /prompts — list all templates, or get one by category&name."""
        qs = urlparse(self.path).query
        cat = self._get_param(qs, "category", "")
        name = self._get_param(qs, "name", "")
        if cat and name:
            tmpl = _pm.get(cat, name)
            if tmpl is None:
                return self._json({"error": f"Prompt not found: {cat}/{name}"}, 404)
            return self._json(tmpl.to_dict())
        return self._json(_pm.snapshot())

    def _prompts_reload(self):
        """POST /prompts/reload — hot-reload from data/prompts.json."""
        try:
            before = _pm.template_count
            _pm.load_file("data/prompts.json")
            after = _pm.template_count
            self._json({"reloaded": True, "before": before, "after": after})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _prompts_preview(self, data):
        """POST /prompts/preview — render a template with given variables."""
        cat = data.get("category", "")
        name = data.get("name", "")
        vars_ = data.get("variables", {})
        if not cat or not name:
            return self._json({"error": "category and name required"}, 400)
        try:
            rendered = _pm.render(cat, name, **vars_)
            self._json({"category": cat, "name": name, "rendered": rendered})
        except KeyError:
            self._json({"error": f"Prompt not found: {cat}/{name}"}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _clear_history(self):
        sid = self._get_param(urlparse(self.path).query, "session_id", "default")
        with chat_lock:
            chat_history.pop(sid, None)
            remaining = len(chat_history)
        self._json({"cleared": True, "active_sessions": remaining})

    def _skills_get(self):
        query = self._get_param(urlparse(self.path).query, "q", "")
        cat = self._get_param(urlparse(self.path).query, "category", "")
        from core.skill_db import skill_registry
        skill_registry.discover()
        if query:
            result = skill_registry.search(query)
        else:
            result = skill_registry.list_all(category=cat if cat else "")
        self._json({"skills": result, "stats": skill_registry.stats()})

    def do_POST(self):
        """处理 POST 请求 - 安全读取请求体，防止超时和大请求攻击"""
        metrics.requests_total += 1
        # 限流检查
        client_ip = self.client_address[0]
        if not rate_limiter.is_allowed(client_ip):
            return self._json({"error": "Too many requests"}, 429)

        # Auth 检查（仅对聊天和 KB 写操作）
        path = urlparse(self.path).path
        if path in ("/chat", "/chat/stream", "/kb/upload", "/kb/add", "/kb/delete"):
            if not check_auth(self):
                return self._json({"error": "Unauthorized"}, 401)

        try:
            content_length = self.headers.get("Content-Length")
            if content_length:
                length = int(content_length)
                if length > 10 * 1024 * 1024:
                    return self._json({"error": "Request too large"}, 413)
                body = self.rfile.read(length)
            else:
                body = b"{}"
        except Exception:
            body = b"{}"

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return self._json({"error": "Invalid JSON"}, 400)

        if path == "/chat":
            self._handle_chat(data, stream=False)
        elif path == "/chat/stream":
            self._handle_chat(data, stream=True)
        elif path == "/kb/upload":
            self._kb_upload(data)
        elif path == "/kb/add":
            self._kb_add_text(data)
        elif path == "/kb/delete":
            self._kb_delete(data)
        elif path == "/prompts/reload":
            if not check_auth(self):
                return self._json({"error": "Unauthorized"}, 401)
            self._prompts_reload()
        elif path == "/prompts/preview":
            if not check_auth(self):
                return self._json({"error": "Unauthorized"}, 401)
            self._prompts_preview(data)
        elif path == "/clear":
            self._clear_history()
        elif path == "/api/tokens/reset":
            tracker.reset()
            self._json({"ok": True})
        else:
            self._json({"error": "not found"}, 404)

    def _kb_upload(self, data):
        """上传文件到知识库"""
        if not kb:
            return self._json({"error": "Knowledge base not enabled"}, 400)
        filepath = data.get("filepath", "")
        content = data.get("content", None)
        if not filepath:
            return self._json({"error": "filepath required"}, 400)
        # 限制路径在 data/docs 内
        abs_path = Path(filepath)
        if not abs_path.is_absolute():
            abs_path = CFG.DOCS / filepath
        # 安全检查：禁止路径遍历
        try:
            abs_path = abs_path.resolve()
            abs_path.relative_to(CFG.DOCS.resolve())
        except ValueError:
            return self._json({"error": "Path outside docs directory"}, 403)
        try:
            result = kb.add_text(content or "", filename=abs_path.name)
            self._json(result)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _kb_add_text(self, data):
        """直接添加文本到知识库"""
        if not kb:
            return self._json({"error": "Knowledge base not enabled"}, 400)
        text = data.get("text", "").strip()
        filename = data.get("filename", "memory.txt")
        if not text:
            return self._json({"error": "text required"}, 400)
        try:
            result = kb.add_text(text, filename)
            self._json(result)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _kb_delete(self, data):
        """从知识库删除文档"""
        if not kb:
            return self._json({"error": "Knowledge base not enabled"}, 400)
        filename = data.get("filename", "")
        if not filename:
            return self._json({"error": "filename required"}, 400)
        # 尝试向量库删除
        try:
            if hasattr(kb, '_vector_kb') and kb._vector_kb:
                ok = kb._vector_kb.delete_document(filename)
            else:
                # 关键词模式：删除文件
                fp = CFG.DOCS / filename
                if fp.exists():
                    fp.unlink()
                    kb.refresh()
                    ok = True
                else:
                    ok = False
            self._json({"deleted": ok, "filename": filename})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _handle_chat(self, data, stream=False):
        """处理聊天请求 - 包含 llm None 检查防止空指针"""
        if stream:
            metrics.stream_requests += 1
        else:
            metrics.chat_requests += 1
        # ========== 空指针保护：检查 llm 是否已加载 ==========
        if llm is None:
            metrics.errors_total += 1
            return self._json({"error": "Model not loaded. Check server startup logs."}, 503)

        prompt = data.get("prompt", "").strip()
        sid = data.get("session_id", "default")
        model_choice = data.get("model", "local")  # local / ollama / deepseek / auto
        prompt_template = data.get("prompt_template", "")  # e.g. "chat/default" or "chat/code_review"
        if not isinstance(sid, str) or len(sid) > 64 or not all(c.isalnum() or c in '_-' for c in sid):
            return self._json({"error": "Invalid session_id"}, 400)
        max_tokens = max(64, min(int(data.get("max_tokens", 512)), 4096))
        temperature = max(0.0, min(float(data.get("temperature", 0.7)), 2.0))

        if not prompt:
            return self._json({"error": "prompt required"}, 400)
        if len(prompt) > 8192:
            return self._json({"error": "prompt too long (max 8192 chars)"}, 400)

        # Resolve system prompt via prompt_manager
        sys_prompt = _pm.render("chat", "default")
        if prompt_template and "/" in prompt_template:
            cat, name = prompt_template.split("/", 1)
            try:
                sys_prompt = _pm.render(cat.strip(), name.strip())
            except KeyError:
                pass  # Fall through to default

        # 初始化历史 + 添加用户消息（LRU 驱逐旧会话）
        with chat_lock:
            if sid not in chat_history:
                while len(chat_history) >= CFG.MAX_CHAT_SESSIONS:
                    chat_history.popitem(last=False)
                chat_history[sid] = [{"role": "system", "content": sys_prompt}]
            else:
                chat_history.move_to_end(sid)
            chat_history[sid].append({"role": "user", "content": prompt})

        # 构建Prompt（含知识库，不污染原始历史）
        formatted, kb_info = self._build_prompt(sid)
        if kb_info.get("error") == "session_not_found":
            return self._json({"error": "Session not found"}, 404)

        if model_choice != "local":
            kb_info["model_used"] = model_choice

        if not chat_queue.acquire(timeout=120):
            return self._json({"error": "Server busy, please retry (concurrent limit reached)"}, 503)
        try:
            if stream:
                self._stream_response(formatted, sid, prompt, max_tokens, temperature, kb_info)
            else:
                self._normal_response(formatted, sid, prompt, max_tokens, temperature, kb_info)
        finally:
            chat_queue.release()

    def _build_prompt(self, sid):
        """构建Prompt — 使用 Token 预算控制输入量，线程安全"""
        kb_info: dict[str, Any] = {"used": False, "sources": [], "engine": "N/A", "token_cost": 0, "context": ""}
        with chat_lock:
            if sid not in chat_history:
                # Session evicted by LRU — shouldn't happen, but guard
                kb_info["error"] = "session_not_found"
                return "", kb_info
            messages = list(chat_history[sid])
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "你是一个有用的AI助手。")
        history = [m for m in messages if m["role"] != "system"]
        user_question = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")

        kb_context = ""
        if kb and user_question:
            try:
                result = kb.query(user_question)
                if isinstance(result, dict) and result.get("has_result"):
                    kb_info = {
                        "used": True,
                        "sources": result.get("sources", []),
                        "engine": result.get("engine", kb.engine_name),
                        "token_cost": result.get("token_cost", 0),
                        "context": result.get("context", ""),
                    }
                    kb_context = kb_info["context"]
            except Exception as e:
                if DEBUG: print(f"  [KB] query error: {e}")

        from core.token_budget import TokenBudget
        budget = TokenBudget(kb_budget=300, max_history_turns=4)
        formatted, budget_info = budget.build_prompt(
            system=system_msg, history=history,
            user_msg=user_question or "(empty)", kb_context=kb_context,
            max_output=512)

        kb_info["token_budget"] = budget_info
        return formatted, kb_info

    def _normal_response(self, formatted, sid, prompt, max_tokens, temperature, kb_info):
        """非流式响应 - 安全解析 LLM 返回结果（30s 超时保护）"""
        import threading as _th
        start = time.time()
        resp_container: list[Any] = [None]
        exc_container: list[Exception | None] = [None]

        def _call():
            try:
                resp_container[0] = llm(formatted, max_tokens=max_tokens, temperature=temperature, stop=["<|im_end|>"])
            except Exception as e:
                exc_container[0] = e

        t = _th.Thread(target=_call, daemon=True)
        t.start()
        t.join(timeout=120)
        if t.is_alive():
            metrics.timeout_errors += 1
            return self._json({"error": "Request timeout (120s)"}, 504)

        if exc_container[0]:
            raise exc_container[0]
        resp = resp_container[0]

        try:
            elapsed = time.time() - start

            # ========== 保护：安全解析 LLM 返回结果，防止空指针 ==========
            if not isinstance(resp, dict):
                raise ValueError(f"Unexpected response type: {type(resp).__name__}")
            choices = resp.get("choices", [])
            if not choices or not isinstance(choices[0], dict):
                raise ValueError("Empty or invalid choices in LLM response")
            text = str(choices[0].get("text", "")).strip()
            tokens = int(resp.get("usage", {}).get("completion_tokens", 0))

            metrics.record_latency(elapsed)
            prompt_tok = kb_info.get("token_budget", {}).get("total_input_tokens", 0)
            metrics.record_tokens(prompt_tok, tokens)
            tracker.record(kb_info.get("model_used", "local"), "server",
                           prompt_tok, tokens)

            with chat_lock:
                chat_history[sid].append({"role": "assistant", "content": text})

            # 记录到数据库
            if db:
                try:
                    from core.token_counter import count
                    db.add_msg(sid, "user", prompt, source="qwen2.5-1.5b", tokens=count(prompt))
                    db.add_msg(sid, "assistant", text, source="qwen2.5-1.5b", tokens=tokens)
                    db.add_sample(instruction=prompt, output=text, source="qwen2.5-1.5b")
                except Exception as db_err:
                    if DEBUG: print(f"  [DB] log error: {db_err}")
            self._trim(sid)

            self._json({
                "response": text, "tokens": tokens,
                "time": round(elapsed, 2),
                "speed": round(tokens / elapsed, 1) if elapsed > 0 else 0,
                "knowledge": kb_info,
            })
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _stream_response(self, formatted, sid, prompt, max_tokens, temperature, kb_info):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send(data):
            self.wfile.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()

        if kb_info["used"]:
            send({"meta": True, "sources": kb_info["sources"], "engine": kb_info["engine"]})

        full_text = ""
        start = time.time()
        try:
            for chunk in llm(formatted, max_tokens=max_tokens, temperature=temperature,
                           stop=["<|im_end|>"], stream=True):
                # ========== 保护：chunk 可能为 None 或非 dict ==========
                chunk_text = ""
                if isinstance(chunk, dict):
                    choices = chunk.get("choices")
                    if isinstance(choices, list) and len(choices) > 0 and isinstance(choices[0], dict):
                        chunk_text = str(choices[0].get("text", ""))
                if chunk_text:
                    token = chunk_text
                    full_text += token
                    send({"token": token, "done": False})

            elapsed = time.time() - start
            result_text = full_text.strip()

            metrics.record_latency(elapsed)
            prompt_tok = kb_info.get("token_budget", {}).get("total_input_tokens", 0)
            metrics.record_tokens(prompt_tok, len(result_text))
            tracker.record(kb_info.get("model_used", "local"), "server",
                           prompt_tok, len(result_text))

            with chat_lock:
                chat_history[sid].append({"role": "assistant", "content": result_text})

            # 记录到数据库
            if db:
                try:
                    from core.token_counter import count
                    db.add_msg(sid, "user", prompt, source="qwen2.5-1.5b", tokens=count(prompt))
                    db.add_msg(sid, "assistant", result_text, source="qwen2.5-1.5b", tokens=count(result_text))
                    db.add_sample(instruction=prompt, output=result_text, source="qwen2.5-1.5b")
                except Exception as db_err:
                    if DEBUG: print(f"  [DB] log error: {db_err}")
            self._trim(sid)

            send({
                "done": True, "full_text": result_text,
                "tokens": len(result_text), "time": round(elapsed, 2),
                "speed": round(len(result_text) / elapsed, 1) if elapsed > 0 else 0,
            })
        except Exception as e:
            send({"error": str(e)})

    def _trim(self, sid, max_msgs=10):
        """Keep at most max_msgs (default: 5 turns). message[0] is system prompt."""
        with chat_lock:
            if len(chat_history[sid]) > max_msgs:
                chat_history[sid] = [chat_history[sid][0]] + chat_history[sid][-(max_msgs - 1):]

    def _get_param(self, query, key, default=""):
        for part in query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                if k == key:
                    return v
        return default

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_file(self, filename):
        # 优先从 static/ 目录查找
        static_dir = Path(__file__).parent.parent.parent / "static"
        fp = static_dir / filename
        if fp.exists():
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(fp, "rb") as f:
                self.wfile.write(f.read())
            return
        self.send_error(404)

    def log_message(self, format, *args):
        if DEBUG:
            print(f"[{time.strftime('%H:%M:%S')}] {args[0]} {args[1]} {args[2]}")


# ============================================================
# 入口
# ============================================================
def main():
    global llm
    print("=" * 50)
    print("  Qwen2.5 统一推理服务")
    print("=" * 50)

    # 配置验证
    warnings = CFG.validate()
    for w in warnings:
        print(f"  [WARN] {w}")

    print(f"  [Model] Primary: {CFG.LOCAL_MODEL} (provider: {CFG.LOCAL_MODEL_PROVIDER})")
    llm = None
    # Try llama-cpp GGUF first, then Ollama
    if CFG.LOCAL_MODEL_PROVIDER == "llama-cpp":
        try:
            from llama_cpp import Llama
            llm = Llama(model_path=CFG.MODEL_PATH, n_ctx=CFG.N_CTX, n_threads=CFG.N_THR, verbose=False)
            from core.llm_bridge import set_llm
            set_llm(llm, backend="llama-cpp")
            print("  [OK] llama-cpp model loaded")
        except ImportError:
            print("  [INFO] llama-cpp-python not installed")
        except Exception as e:
            print(f"  [INFO] llama-cpp load failed: {e}")
    if llm is None:
        try:
            from core.llm_bridge import create_ollama_llm, set_llm
            import requests as _r
            _r.get(f"{CFG.OLLAMA_URL}/api/tags", timeout=5)
            llm = create_ollama_llm(model=CFG.LOCAL_MODEL, base_url=CFG.OLLAMA_URL)
            set_llm(llm, backend="ollama")
            print(f"  [OK] Ollama connected: {CFG.LOCAL_MODEL}")
        except Exception as e:
            print(f"  [INFO] Ollama unavailable: {e}")
            print("  [INFO] /chat endpoint will use fallback")

    if CFG.API_KEY:
        print(f"  [Auth] API key authentication enabled")

    if kb:
        try:
            kbs = kb.stats() if hasattr(kb, 'stats') else {}
            kbd = kbs.get("documents", 0)
        except Exception:
            kbd = 0
        print(f"  [KB] {kb.engine_name} [{kbd} chunks]")
    else:
        print("  [KB] Disabled (USE_KB=1 to enable)")

    if db:
        stats = db.stats()
        print(f"  [DB] {stats['messages']} msgs, {stats['samples']} samples")
    else:
        print("  [DB] Disabled")

    # Start autonomous task scheduler
    try:
        from core.scheduler import scheduler as sched
        from plugins.agent import AgentSwarm
        sched.add("kb_incremental_scan", lambda: kb._scan(incremental=True) if kb else None, every_seconds=120)
        AgentSwarm.register_scheduled_tasks(sched)
        sched.start()
        print("  [Auto] Scheduler started with autonomous tasks")
    except Exception as e:
        if DEBUG: print(f"  [Auto] Scheduler init failed: {e}")

    print(f"\n  [Web] http://localhost:{CFG.PORT}")
    print("  [API] POST /chat            - Chat (prompt_template optional)")
    print("  [API] POST /chat/stream     - Stream chat")
    print("  [API] GET  /                - Web UI")
    print("  [API] GET  /health          - Health check")
    print("  [API] GET  /ping            - Ping (public)")
    print("  [API] GET  /metrics         - Metrics (auth)")
    print("  [API] GET  /tokens          - Token 监控面板")
    print("  [API] GET  /api/tokens      - Token 统计数据 (JSON)")
    print("  [API] GET  /scheduler       - Task scheduler status")
    print("")
    print("  [API] GET  /memory          - Agent memory stats")
    print("  [API] GET  /kb/status       - KB status")
    print("  [API] POST /kb/upload       - Upload document")
    print("  [API] POST /kb/add          - Add text to KB")
    print("  [API] POST /kb/delete       - Delete from KB")
    print("  [API] GET  /db/stats        - DB stats (auth required)")
    print("  [API] GET  /prompts         - List prompt templates (auth)")
    print("  [API] POST /prompts/reload  - Hot-reload prompts (auth)")
    print("  [API] POST /prompts/preview - Render prompt preview (auth)")
    if CFG.API_KEY:
        print("\n  [Auth] Set Authorization: Bearer <key> for POST endpoints")
    print("=" * 50)
    print("  Ctrl+C to stop\n")

    server = HTTPServer(("0.0.0.0", CFG.PORT), Handler)
    server.socket.settimeout(120)

    # Signal handlers only work in main thread
    try:
        import signal as _signal
        def _shutdown(signum, frame):
            print("\n  Shutting down...")
            server.shutdown()
        _signal.signal(_signal.SIGINT, _shutdown)
        _signal.signal(_signal.SIGTERM, _shutdown)
    except ValueError:
        pass  # Running in a daemon thread — shutdown via KeyboardInterrupt

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if db:
            db.close()
        print("  Server stopped.")


if __name__ == "__main__":
    main()
