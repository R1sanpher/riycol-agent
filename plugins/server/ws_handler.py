"""
WebSocket handler for bidirectional real-time chat.
===================================================
Upgrades HTTP GET /ws to WebSocket. Supports:
  - Bidirectional JSON messaging
  - Server-side stop (client sends {"cmd":"stop"})
  - Token-by-token streaming
  - Multiplexed sessions

No external dependencies — pure stdlib implementation.
"""
import hashlib, base64, struct, json, time, uuid
from http.server import BaseHTTPRequestHandler
from core.logger import log
from core.config import CFG

WS_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _accept_key(key: str) -> str:
    digest = hashlib.sha1(key.encode() + WS_MAGIC).digest()
    return base64.b64encode(digest).decode()


def _encode_frame(payload: bytes | str, opcode: int = 0x1) -> bytes:
    """Encode a WebSocket text frame."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    length = len(payload)
    frame = bytearray([0x80 | opcode])  # FIN + opcode
    if length < 126:
        frame.append(length)
    elif length < 65536:
        frame.append(126)
        frame.extend(struct.pack(">H", length))
    else:
        frame.append(127)
        frame.extend(struct.pack(">Q", length))
    frame.extend(payload)
    return bytes(frame)


def _decode_frame(data: bytes) -> tuple[int, bytes, int] | None:
    """Decode a WebSocket frame. Returns (opcode, payload, consumed_bytes) or None."""
    if len(data) < 2:
        return None
    opcode = data[0] & 0x0F
    masked = (data[1] & 0x80) != 0
    length = data[1] & 0x7F
    offset = 2
    if length == 126:
        if len(data) < 4:
            return None
        length = struct.unpack(">H", data[2:4])[0]
        offset = 4
    elif length == 127:
        if len(data) < 10:
            return None
        length = struct.unpack(">Q", data[2:10])[0]
        offset = 10
    mask_offset = offset
    if masked:
        if len(data) < offset + 4:
            return None
        offset += 4
        mask = data[mask_offset:offset]
    if len(data) < offset + length:
        return None
    payload = bytearray(data[offset:offset + length])
    if masked:
        for i in range(length):
            payload[i] ^= mask[i % 4]
    consumed = offset + length
    return opcode, bytes(payload), consumed


def handle_ws_upgrade(handler: BaseHTTPRequestHandler) -> bool:
    """Attempt WebSocket upgrade. Returns True if upgraded."""
    if handler.path != "/ws":
        return False

    # Validate Origin header to prevent cross-site WebSocket hijacking
    origin = handler.headers.get("Origin", "")
    if origin:
        allowed = _is_origin_allowed(origin)
        if not allowed:
            log.warn(f"WS: rejected Origin={origin}")
            handler.send_error(403)
            return False

    key = handler.headers.get("Sec-WebSocket-Key", "")
    if not key:
        handler.send_error(400)
        return False
    accept = _accept_key(key)
    handler.send_response(101)
    handler.send_header("Upgrade", "websocket")
    handler.send_header("Connection", "Upgrade")
    handler.send_header("Sec-WebSocket-Accept", accept)
    handler.end_headers()
    return True


def _is_origin_allowed(origin: str) -> bool:
    """Allow localhost origins and the configured server host."""
    if not origin:
        return True  # no Origin header = same-origin
    allowed = {"http://localhost", "http://127.0.0.1", f"http://localhost:{CFG.PORT}"}
    return origin in allowed


def ws_chat_loop(handler: BaseHTTPRequestHandler):
    """
    Main WebSocket chat loop.
    Expects JSON messages: {"type":"chat", "prompt":"...", "session_id":"...", "temperature":0.7, "max_tokens":1024}
    Client can send: {"type":"stop"} to abort generation.
    """
    from plugins.server.handler import llm, chat_history, chat_lock, db, kb
    from core.token_tracker import tracker as _tt

    buf = b""
    running = True
    sid = "ws_" + uuid.uuid4().hex[:12]
    stop_flag = False
    # Last activity time for idle timeout
    last_activity = time.time()

    def ws_send(data: dict):
        try:
            handler.wfile.write(_encode_frame(json.dumps(data, ensure_ascii=False)))
            handler.wfile.flush()
        except Exception:
            nonlocal running
            running = False

    while running:
        try:
            handler.request.settimeout(5.0)  # per-read timeout
            chunk = handler.rfile.read(4096)
            if not chunk:
                break
            last_activity = time.time()
            buf += chunk
            while True:
                result = _decode_frame(buf)
                if not result:
                    break
                opcode, payload, consumed = result
                buf = buf[consumed:]  # Advance past consumed bytes

                if opcode == 0x8:  # Close
                    ws_send({"type": "closed"})
                    return
                if opcode == 0x9:  # Ping
                    handler.wfile.write(_encode_frame(b"", 0xA))  # Pong
                    last_activity = time.time()
                    continue

                try:
                    msg = json.loads(payload.decode("utf-8"))
                except Exception:
                    continue

                cmd = msg.get("type", "")
                if cmd == "stop":
                    stop_flag = True
                    ws_send({"type": "stopped"})
                    continue

                if cmd != "chat":
                    ws_send({"type": "error", "error": f"Unknown command: {cmd}"})
                    continue

                prompt = msg.get("prompt", "").strip()
                if not prompt:
                    ws_send({"type": "error", "error": "prompt required"})
                    continue

                sid = msg.get("session_id", sid)
                temperature = max(0.0, min(float(msg.get("temperature", 0.7)), 2.0))
                max_tokens = max(64, min(int(msg.get("max_tokens", 512)), 4096))

                # Build prompt with KB context — acquire lock for chat_history access
                with chat_lock:
                    if sid not in chat_history:
                        chat_history[sid] = [{"role": "system", "content": "你是一个有用的AI助手。"}]
                    chat_history[sid].append({"role": "user", "content": prompt})
                    messages = list(chat_history[sid])

                formatted, kb_info = _build_ws_prompt(sid, kb, messages)
                full_text = ""
                start = time.time()
                stop_flag = False

                try:
                    for token_chunk in llm(formatted, max_tokens=max_tokens,
                                           temperature=temperature, stop=["<|im_end|>"], stream=True):
                        if stop_flag:
                            break
                        chunk_text = ""
                        if isinstance(token_chunk, dict):
                            choices = token_chunk.get("choices")
                            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                                chunk_text = str(choices[0].get("text", ""))
                        if chunk_text:
                            full_text += chunk_text
                            ws_send({"type": "token", "token": chunk_text})

                    elapsed = time.time() - start
                    result_text = full_text.strip()

                    _tt.record("local", "server",
                               len(formatted) // 4, len(result_text) // 4)

                    with chat_lock:
                        if sid in chat_history:
                            chat_history[sid].append({"role": "assistant", "content": result_text})

                    ws_send({
                        "type": "done",
                        "full_text": result_text,
                        "tokens": len(result_text),
                        "time": round(elapsed, 2),
                        "knowledge": kb_info,
                    })

                    if db:
                        try:
                            db.add_msg(sid, "user", prompt, source="ws", tokens=len(prompt))
                            db.add_msg(sid, "assistant", result_text, source="ws", tokens=len(result_text))
                        except Exception:
                            pass

                except Exception as e:
                    ws_send({"type": "error", "error": str(e)})

        except (OSError, TimeoutError):
            # Read timeout — send ping to keep connection alive
            if time.time() - last_activity > 300:  # 5 min idle
                break
            try:
                handler.wfile.write(_encode_frame(b"", 0x9))  # Ping
                handler.wfile.flush()
            except Exception:
                break
        except Exception as e:
            log.error(f"WS loop error: {e}")
            break


def _build_ws_prompt(sid: str, kb, messages: list = None) -> tuple[str, dict]:
    """Build prompt for WebSocket chat (mirrors handler._build_prompt)."""
    kb_info = {"used": False, "sources": [], "engine": "N/A", "token_cost": 0, "context": ""}
    if not messages:
        return "", kb_info
    user_question = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
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
                for i, msg in enumerate(messages):
                    if msg["role"] == "system":
                        messages[i] = {"role": "system",
                                       "content": msg["content"] + f"\n\n【参考资料】\n{kb_info['context']}"}
                        break
        except Exception:
            pass
    parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages]
    parts.append("<|im_start|>assistant\n")
    return "".join(parts), kb_info
