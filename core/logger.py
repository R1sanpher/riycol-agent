import sys, io, logging, uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from core.config import CFG

LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warn": logging.WARNING, "error": logging.ERROR}


class Logger:
    def __init__(self, level="info", log_dir=None, max_bytes=5 * 1024 * 1024, backup_count=3):
        self._logger = logging.getLogger("riycol")
        self._logger.setLevel(LEVELS.get(level, logging.INFO))
        self._logger.handlers.clear()

        fmt = logging.Formatter("%(asctime)s [%(levelname).1s] %(message)s", datefmt="%H:%M:%S")

        utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', write_through=True)
        console = logging.StreamHandler(utf8_stdout)
        console.setFormatter(fmt)
        self._logger.addHandler(console)

        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                Path(log_dir) / "riycol.log", maxBytes=max_bytes,
                backupCount=backup_count, encoding="utf-8")
            file_handler.setFormatter(fmt)
            self._logger.addHandler(file_handler)

    def debug(self, msg): self._logger.debug(msg)
    def info(self, msg): self._logger.info(msg)
    def warn(self, msg): self._logger.warning(msg)
    def error(self, msg): self._logger.error(msg)

    def traced(self, level: str, msg: str, trace_id: str = "", **kwargs: Any) -> str:
        """Structured log with trace ID and optional key-value pairs."""
        tid = trace_id or new_trace_id()
        extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
        full = f"[trace={tid[:8]}] {msg}" + (f" | {extra}" if extra else "")
        method: Any = getattr(self._logger, level)
        method(full)
        return tid


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


log = Logger(level=CFG.LOG_LEVEL)
