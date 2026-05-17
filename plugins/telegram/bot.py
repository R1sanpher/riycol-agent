import time
import threading
import re
import requests
from concurrent.futures import ThreadPoolExecutor
from core.config import CFG
from core.logger import log
from plugins.telegram.stats import MessageStats
from plugins.telegram.ai import AIChat

TELEGRAM_MAX_MSG_LEN = 4096
MAX_WORKERS = 10


class TelegramBot:
    def __init__(self):
        self.ai = AIChat(model=CFG.TG_MODEL)
        self.stats = MessageStats()
        self.running = False
        self._thread = None
        self.offset = 0
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self._load_offset()
        # Parse allowed users from comma-separated string
        self._allowed_users: set[int] = set()
        allowed_str = CFG.TELEGRAM_ALLOWED
        if allowed_str:
            for part in allowed_str.split(","):
                part = part.strip()
                if part.isdigit():
                    try:
                        self._allowed_users.add(int(part))
                    except (ValueError, OverflowError):
                        log.warn(f"Telegram: invalid allowed user id: {part}")
        # Proxy for Telegram API
        self._proxy = None
        proxy_url = CFG.TG_PROXY
        if proxy_url:
            self._proxy = {"http": proxy_url, "https": proxy_url}
            log.info(f"Telegram proxy: {proxy_url}")

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        log.info("Telegram bot started")

    def _load_offset(self):
        try:
            from core.memory_store import memory_store
            self.offset = memory_store.get("telegram", "offset", 0)
            if self.offset:
                log.info(f"Telegram offset restored: {self.offset}")
        except Exception:
            self.offset = 0

    def _save_offset(self):
        try:
            from core.memory_store import memory_store
            memory_store.put("telegram", "offset", self.offset)
        except Exception:
            pass

    def stop(self):
        self.running = False
        self._save_offset()
        log.info("Telegram bot stopped")
        self._executor.shutdown(wait=False)
        log.info("Telegram bot stopped")

    def _poll_loop(self):
        retry = 1
        while self.running:
            try:
                url = f"https://api.telegram.org/bot{CFG.TELEGRAM_TOKEN}/getUpdates"
                params = {"offset": self.offset, "timeout": 30}
                resp = requests.get(url, params=params, timeout=35, proxies=self._proxy)
                data = resp.json()
                if data.get("ok"):
                    retry = 1
                    for update in data.get("result", []):
                        self.offset = update["update_id"] + 1
                        self._save_offset()
                        self._executor.submit(self._handle_update, update)
                else:
                    log.warn(f"Telegram poll bad response: {data}")
            except Exception as e:
                log.error(f"Telegram poll error: {e}")
                wait = min(retry, 30)  # 指数退避，最大30秒
                time.sleep(wait)
                retry = min(retry * 2, 60)  # 1,2,4,8... 最大60

    def _handle_update(self, update):
        if "message" not in update:
            return
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        user_id = msg["from"]["id"]
        text = msg.get("text", "")

        # Check allowed users
        if self._allowed_users and user_id not in self._allowed_users:
            return

        if not text:
            return

        # Check blacklist (word-boundary + case-insensitive)
        blacklist_str = CFG.BLACKLIST_KEYWORDS
        if blacklist_str:
            for kw in blacklist_str.split(","):
                kw = kw.strip()
                if kw and re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
                    log.warn(f"Telegram blocked keyword '{kw}': {text[:30]}")
                    return

        self.stats.record_received(str(user_id))
        log.info(f"Telegram msg from {user_id}: {text[:50]}")

        # Send typing indicator before processing
        self._send_chat_action(chat_id, "typing")

        t0 = time.time()
        reply = self.ai.get_reply(str(user_id), text)
        elapsed = time.time() - t0
        log.info(f"Telegram reply in {elapsed:.1f}s ({len(reply)} chars)")

        self._send_message(chat_id, reply)
        self.stats.record_sent(str(user_id))

    def _send_chat_action(self, chat_id, action="typing"):
        """Send chat action indicator (typing, upload_photo, etc.)."""
        try:
            url = f"https://api.telegram.org/bot{CFG.TELEGRAM_TOKEN}/sendChatAction"
            requests.post(url, data={"chat_id": chat_id, "action": action}, timeout=5, proxies=self._proxy)
        except Exception:
            pass  # Non-critical, swallow failures silently

    def _send_message(self, chat_id, text):
        """Send message, splitting if over Telegram's 4096 char limit."""
        chunks = self._split_text(text)
        for chunk in chunks:
            self._send_single(chat_id, chunk)

    def _split_text(self, text: str) -> list[str]:
        """Split long text at paragraph boundaries to fit Telegram limits."""
        if len(text) <= TELEGRAM_MAX_MSG_LEN:
            return [text]
        chunks = []
        while len(text) > TELEGRAM_MAX_MSG_LEN:
            split_at = text.rfind("\n", 0, TELEGRAM_MAX_MSG_LEN)
            if split_at == -1:
                split_at = text.rfind(" ", 0, TELEGRAM_MAX_MSG_LEN)
            if split_at == -1:
                split_at = TELEGRAM_MAX_MSG_LEN
            chunks.append(text[:split_at].strip())
            text = text[split_at:].strip()
        if text:
            chunks.append(text)
        return chunks

    @staticmethod
    def _md_to_telegram_html(text: str) -> str:
        """Convert common Markdown to Telegram HTML parse mode.
        **bold** → <b>bold</b>, strip ### headings, etc."""
        # Bold: **text** → <b>text</b>
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        # Italic: *text* → <i>text</i> (but not **)
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
        # Inline code: `text` → <code>text</code>
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        # Strip heading markers (###, ##, #) — not supported in TG
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Escape residual HTML chars that are not our tags
        text = text.replace('&', '&amp;').replace('<b>', '\x00b\x00').replace('<i>', '\x00i\x00').replace('<code>', '\x00c\x00')
        text = text.replace('</b>', '\x00/b\x00').replace('</i>', '\x00/i\x00').replace('</code>', '\x00/c\x00')
        text = text.replace('<', '&lt;').replace('>', '&gt;')
        text = text.replace('\x00b\x00', '<b>').replace('\x00i\x00', '<i>').replace('\x00c\x00', '<code>')
        text = text.replace('\x00/b\x00', '</b>').replace('\x00/i\x00', '</i>').replace('\x00/c\x00', '</code>')
        text = text.replace('&amp;', '&')
        return text

    def _send_single(self, chat_id, text):
        html_text = self._md_to_telegram_html(text)
        for attempt in range(3):
            try:
                url = f"https://api.telegram.org/bot{CFG.TELEGRAM_TOKEN}/sendMessage"
                data = {"chat_id": chat_id, "text": html_text, "parse_mode": "HTML"}
                resp = requests.post(url, data=data, timeout=10, proxies=self._proxy)
                if resp.ok:
                    log.info(f"Telegram replied: {text[:50]}")
                    return
                # parse_mode error → fallback to plain text
                if resp.status_code == 400:
                    data.pop("parse_mode")
                    data["text"] = text
                    resp = requests.post(url, data=data, timeout=10, proxies=self._proxy)
                    if resp.ok:
                        return
                log.warn(f"Telegram send HTTP {resp.status_code}")
            except Exception as e:
                log.error(f"Telegram send error (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
