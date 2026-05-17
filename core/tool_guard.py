"""
Poka-Yoke Tool Guards — make tool errors hard to make.

Constrained parameter validation for built-in tools.
Inspired by Anthropic's recommendation: "design arguments to make mistakes difficult."
"""
import re, os
from pathlib import Path
from typing import Any
from core.logger import log
from core.config import CFG


# ---- Path safety ----

def resolve_path(filepath: str) -> Path:
    """Resolve filepath within project root. Auto-completes relative paths.
    Rejects absolute paths outside project. Raises ValueError on violation.
    """
    root = CFG.ROOT.resolve()
    p = Path(filepath)
    if not p.is_absolute():
        p = root / p

    # Auto-complete if file exists nearby
    if not p.exists():
        stem = p.stem
        parent = p.parent if p.parent.exists() else root
        candidates = list(parent.glob(f"{stem}*"))
        if len(candidates) == 1:
            p = candidates[0]
            log.debug(f"ToolGuard: auto-completed path to {p.name}")

    p = p.resolve()
    try:
        p.relative_to(root)
    except ValueError:
        raise ValueError(f"Path outside project: {filepath}")

    return p


# ---- SQL safety ----

FORBIDDEN_SQL = re.compile(
    r'\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|REPLACE)\b',
    re.IGNORECASE
)
ALLOWED_SQL = re.compile(r'\bSELECT\b', re.IGNORECASE)


def validate_sql(sql: str) -> str:
    """Validate SQL query is read-only. Raises ValueError on violation."""
    stripped = sql.strip()
    if FORBIDDEN_SQL.search(stripped):
        raise ValueError(f"Write operation blocked in tool query: {stripped[:80]}")
    if not ALLOWED_SQL.search(stripped):
        raise ValueError(f"Only SELECT queries allowed: {stripped[:80]}")
    return stripped


# ---- URL safety ----

ALLOWED_DOMAINS = [
    "github.com", "pypi.org", "python.org", "wikipedia.org",
    "stackoverflow.com", "docs.python.org", "arxiv.org",
    "huggingface.co", "ollama.com", "api.deepseek.com",
    "notion.so", "bilibili.com", "anthropic.com",
]


def validate_url(url: str) -> str:
    """Validate URL is from an allowed domain. Blocks suspicious URLs."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if not domain:
        raise ValueError(f"Invalid URL: no domain in {url[:80]}")

    # Check against allowed list
    for allowed in ALLOWED_DOMAINS:
        if domain == allowed or domain.endswith("." + allowed):
            return url

    # Allow localhost
    if domain.startswith("127.") or domain == "localhost" or "localhost:" in domain:
        return url

    # Block internal/private IPs
    if re.match(r'^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)', domain):
        raise ValueError(f"Internal network URL blocked: {domain}")

    # Unknown domain: allow but log
    log.warn(f"ToolGuard: url to unknown domain '{domain}', allowing with caution")
    return url


# ---- File sanitization ----

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
BINARY_EXTENSIONS = {".exe", ".dll", ".pyd", ".so", ".bin", ".png", ".jpg",
                     ".jpeg", ".gif", ".pyc", ".zip", ".tar", ".gz", ".7z",
                     ".mp3", ".mp4", ".avi", ".mov", ".pdf", ".docx", ".gguf"}


def validate_file_size(filepath: str, max_bytes: int = MAX_FILE_SIZE) -> Path:
    """Validate file exists and is within size limits. Returns resolved Path."""
    p = resolve_path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if p.stat().st_size > max_bytes:
        raise ValueError(f"File too large ({p.stat().st_size} > {max_bytes} bytes): {filepath}")
    if p.suffix.lower() in BINARY_EXTENSIONS:
        raise ValueError(f"Binary files not readable: {filepath}")
    return p


# ---- WebFetch safety ----

DEFAULT_MAX_CHARS = 3000
DEFAULT_TIMEOUT = 10
MAX_TIMEOUT = 30
MAX_MAX_CHARS = 10000


def validate_web_fetch(url: str, max_chars: int = DEFAULT_MAX_CHARS,
                       timeout: int = DEFAULT_TIMEOUT) -> tuple[str, int, int]:
    """Validate web_fetch parameters. Returns (url, max_chars, timeout)."""
    url = validate_url(url)
    max_chars = min(max(max_chars, 100), MAX_MAX_CHARS)
    timeout = min(max(timeout, 3), MAX_TIMEOUT)
    return url, max_chars, timeout
