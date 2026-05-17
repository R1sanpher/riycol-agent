import os
from pathlib import Path


def _safe_int(val: str, default: int) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_bool(val: str) -> bool:
    return val.lower() in ("1", "true", "yes", "on") if val else False


class Config:
    """Centralized configuration — all env var reads go through CFG.

    Usage::
        from core.config import CFG
        CFG.PORT          # int, reads from env or .env
        CFG.DEBUG         # bool
        CFG.reload()      # re-read .env into os.environ

    Each property reads from ``os.environ`` live (no stale cache), so
    tests that temporarily set env vars work without calling reload().
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    # ── file loader ──────────────────────────────────────────

    def _init(self):
        self._root = Path(__file__).parent.parent.resolve()
        self._load_env_file(self._root / ".env", override=False)

    @staticmethod
    def _load_env_file(path: Path, override: bool = False):
        """Parse a .env file into os.environ (no-op if missing)."""
        if not path.exists():
            return
        raw = path.read_text(encoding="utf-8", errors="replace")
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if override:
                os.environ[k] = v
            else:
                os.environ.setdefault(k, v)

    def reload(self):
        """Re-read .env with override so changes take effect immediately."""
        self._load_env_file(self._root / ".env", override=True)

    # ── paths ────────────────────────────────────────────────

    @property
    def ROOT(self):
        return self._root

    @property
    def DATA(self):
        return self._root / "data"

    @property
    def DOCS(self):
        return self._root / "data" / "docs"

    # ── Server ───────────────────────────────────────────────

    @property
    def PORT(self):
        return _safe_int(os.environ.get("PORT", "8000"), 8000)

    @property
    def DEBUG(self):
        return _safe_bool(os.environ.get("DEBUG", "0"))

    @property
    def API_KEY(self):
        return os.environ.get("API_KEY", "")

    @property
    def MAX_CHAT_SESSIONS(self):
        return _safe_int(os.environ.get("MAX_CHAT_SESSIONS", "500"), 500)

    # ── Local Model (Ollama / llama-cpp) ─────────────────────

    @property
    def LOCAL_MODEL_PROVIDER(self):
        return os.environ.get("LOCAL_MODEL_PROVIDER", "ollama")

    @property
    def OLLAMA_URL(self):
        return os.environ.get("OLLAMA_URL", "http://localhost:11434")

    @property
    def OLLAMA_MODEL(self):
        return os.environ.get("OLLAMA_MODEL", "gemma4-e4b")

    @property
    def LOCAL_MODEL(self):
        return self.OLLAMA_MODEL

    @property
    def MODEL_PATH(self):
        return os.environ.get("MODEL_PATH", str(self._root / "models" / "qwen2.5-1.5b.gguf"))

    @property
    def N_CTX(self):
        return _safe_int(os.environ.get("N_CTX", "2048"), 2048)

    @property
    def N_THR(self):
        return _safe_int(os.environ.get("N_THREADS", "8"), 8)

    @property
    def MMPROJ_PATH(self):
        return os.environ.get("MMPROJ_PATH", "")

    @property
    def HF_MIRROR(self):
        return os.environ.get("HF_MIRROR", "https://huggingface.co")

    # ── DeepSeek Cloud ───────────────────────────────────────

    @property
    def DEEPSEEK_KEY(self):
        return os.environ.get("DEEPSEEK_API_KEY", "")

    @property
    def DEEPSEEK_URL(self):
        return os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

    # ── Telegram ─────────────────────────────────────────────

    @property
    def TELEGRAM_TOKEN(self):
        return os.environ.get("TELEGRAM_BOT_TOKEN", "")

    @property
    def TELEGRAM_ALLOWED(self):
        return os.environ.get("TELEGRAM_ALLOWED_USERS", "")

    @property
    def TG_PROXY(self):
        return os.environ.get("TG_PROXY", "")

    @property
    def TG_MODEL(self):
        return os.environ.get("TG_MODEL", "auto")

    # ── Discord ────────────────────────────────────────────

    @property
    def DISCORD_BOT_TOKEN(self):
        return os.environ.get("DISCORD_BOT_TOKEN", "")

    @property
    def DISCORD_ALLOWED_USERS(self):
        return os.environ.get("DISCORD_ALLOWED_USERS", "")

    @property
    def DISCORD_MODEL(self):
        return os.environ.get("DISCORD_MODEL", "auto")

    # ── Notion ───────────────────────────────────────────────

    @property
    def NOTION_KEY(self):
        return os.environ.get("NOTION_API_KEY", "")

    @property
    def NOTION_PROXY(self):
        return os.environ.get("NOTION_PROXY", self.TG_PROXY)

    # ── Knowledge Base ───────────────────────────────────────

    @property
    def USE_KB(self):
        return _safe_bool(os.environ.get("USE_KB", "1"))

    @property
    def KB_MODE(self):
        return os.environ.get("KB_MODE", "hybrid")

    @property
    def EMBEDDING_MODEL(self):
        return os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    @property
    def VECTOR_KB_PATH(self):
        return os.environ.get("VECTOR_KB_PATH", str(self.DATA / "chroma_db"))

    # ── Database ─────────────────────────────────────────────

    @property
    def USE_DB(self):
        return _safe_bool(os.environ.get("USE_DB", "1"))

    @property
    def DB_PATH(self):
        return str(self.DATA / "database.db")

    # ── Conversation ─────────────────────────────────────────

    @property
    def CONTEXT_ROUNDS(self):
        return _safe_int(os.environ.get("CONTEXT_ROUNDS", "3"), 3)

    # ── Log ──────────────────────────────────────────────────

    @property
    def LOG_LEVEL(self):
        return os.environ.get("LOG_LEVEL", "info")

    # ── Safety ───────────────────────────────────────────────

    @property
    def BLACKLIST_KEYWORDS(self):
        return os.environ.get("BLACKLIST_KEYWORDS", "")

    # ── Validation ───────────────────────────────────────────

    def validate(self) -> list[str]:
        warnings: list[str] = []
        if not self.DEEPSEEK_KEY:
            warnings.append("DEEPSEEK_API_KEY not set: AI features disabled")
        if not self.TELEGRAM_TOKEN:
            warnings.append("TELEGRAM_BOT_TOKEN not set: Telegram plugin disabled")
        if not self.DISCORD_BOT_TOKEN:
            warnings.append("DISCORD_BOT_TOKEN not set: Discord plugin disabled")
        if self.LOCAL_MODEL_PROVIDER == "llama-cpp" and not Path(self.MODEL_PATH).exists():
            warnings.append(f"MODEL_PATH not found: {self.MODEL_PATH}")
        if self.PORT < 1 or self.PORT > 65535:
            warnings.append(f"PORT {self.PORT} out of range (1-65535)")
        if self.N_CTX < 256:
            warnings.append(f"N_CTX {self.N_CTX} too small (min 256)")
        return warnings


CFG = Config()
