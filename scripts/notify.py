"""Send Telegram notification. Usage: python scripts/notify.py "message"
Chat ID priority: TELEGRAM_ALLOWED_USERS env → memory_store → CLI arg.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import requests
from core.config import CFG
from core.memory_store import memory_store as mem
from core.logger import log


def get_chat_id() -> str:
    """Resolve notification chat ID from config or memory."""
    # From env
    allowed = CFG.TELEGRAM_ALLOWED
    if allowed:
        return allowed.split(",")[0].strip()
    # From memory store
    cid = mem.get("telegram", "chat_id", "")
    if cid:
        return str(cid)
    # From CLI arg
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        return sys.argv[1]
    return ""


def send_notification(message: str, chat_id: str = "") -> bool:
    """Send a message via Telegram bot. Returns True on success."""
    cid = chat_id or get_chat_id()
    if not cid:
        log.error("Notify: no chat_id configured")
        return False

    url = f"https://api.telegram.org/bot{CFG.TELEGRAM_TOKEN}/sendMessage"
    proxies = {"https": CFG.TG_PROXY} if CFG.TG_PROXY else None
    try:
        r = requests.post(url, data={
            "chat_id": cid, "text": message,
            "parse_mode": "Markdown", "disable_web_page_preview": True
        }, timeout=10, proxies=proxies)
        ok = r.json().get("ok", False)
        if ok:
            log.info(f"Notify sent to {cid}: {message[:50]}")
        else:
            log.error(f"Notify fail: {r.json()}")
        return ok
    except Exception as e:
        log.error(f"Notify error: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/notify.py <message> [chat_id]")
        cid = get_chat_id()
        print(f"  Chat ID: {'set='+cid if cid else 'NOT CONFIGURED'}")
        sys.exit(1)
    msg = sys.argv[1]
    cid = sys.argv[2] if len(sys.argv) > 2 else ""
    ok = send_notification(msg, cid)
    sys.exit(0 if ok else 1)
