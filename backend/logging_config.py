"""
Centralized logging setup for Mykare Voice AI.
Import get_logger() in every module — do not configure logging elsewhere.

Log files: logs/mykare.log  (rotates at 10 MB, keeps 5 backups)
Console  : colored output for easy reading during development
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

# ── ANSI colors for console ───────────────────────────────────────────────────
GREY    = "\033[38;5;240m"
CYAN    = "\033[36m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
BOLD_RED= "\033[1;31m"
RESET   = "\033[0m"

LEVEL_COLORS = {
    "DEBUG":    GREY,
    "INFO":     GREEN,
    "WARNING":  YELLOW,
    "ERROR":    RED,
    "CRITICAL": BOLD_RED,
}


class ColorFormatter(logging.Formatter):
    FMT = "%(asctime)s | {color}%(levelname)-8s{reset} | %(name)s:%(funcName)s:%(lineno)d | %(message)s"

    def format(self, record: logging.LogRecord) -> str:
        color = LEVEL_COLORS.get(record.levelname, RESET)
        formatter = logging.Formatter(
            self.FMT.format(color=color, reset=RESET),
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        return formatter.format(record)


class PlainFormatter(logging.Formatter):
    FMT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"

    def __init__(self):
        super().__init__(self.FMT, datefmt="%Y-%m-%d %H:%M:%S")


_configured = False


def configure_logging(level: str = "DEBUG") -> None:
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.DEBUG))

    # ── Console handler ───────────────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(ColorFormatter())
    root.addHandler(console)

    # ── Rotating file handler ─────────────────────────────────────────────────
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "mykare.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(PlainFormatter())
    root.addHandler(file_handler)

    # Quiet noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "websockets", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root.info("Logging initialised — console + %s (rotating 10 MB × 5)", log_file)


def get_logger(name: str) -> logging.Logger:
    """
    Call once at module top-level:
        from logging_config import get_logger
        log = get_logger(__name__)
    """
    configure_logging()
    return logging.getLogger(name)
