"""nl2cmd — Natural-language to PowerShell command generator via Ollama."""
import re
import requests
from core.config import CFG
from core.logger import log

SYSTEM_PROMPT = (
    "You are a PowerShell command generator. "
    "Output ONLY the raw command. "
    "No thinking, no explanation, no markdown."
)


def generate_command(prompt: str) -> str:
    """Send prompt to Ollama, return cleaned command string."""
    log.info(f"nl2cmd: generating command for '{prompt[:60]}...'")
    resp = requests.post(
        f"{CFG.OLLAMA_URL}/api/chat",
        json={
            "model": CFG.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data.get("message", {}).get("content", "")
    # Strip Qwen3 think blocks
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()
    if not text:
        raise RuntimeError("Ollama returned empty response")
    log.info(f"nl2cmd: generated '{text[:80]}...'")
    return text
