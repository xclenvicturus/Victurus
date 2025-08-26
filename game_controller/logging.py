# game_controller/logging.py
# Lightweight, centralized logging utilities for Victurus.
# - Simple setup() that can log to console and/or a rotating file
# - Plain text or JSON formatting
# - A sink factory that returns Callable[[str], None] for simulator debug piping

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable


__all__ = [
    "setup",
    "get_logger",
    "install_global_excepthook",
    "make_sink",
    "LogSetup",
]


# -------------------------
# Dataclass for setup opts
# -------------------------

@dataclass
class LogSetup:
    level: int = logging.INFO
    to_console: bool = True
    log_file: Optional[str] = None
    rotate_by_size: bool = True
    max_bytes: int = 5_000_000
    backup_count: int = 3
    as_json: bool = False
    # Example JSON schema
    json_fields: tuple[str, ...] = ("time", "level", "name", "message")


# -------------------------
# Formatters
# -------------------------

class PlainFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        # ISO-like time with milliseconds
        dt = datetime.fromtimestamp(record.created)
        return dt.strftime("%Y-%m-%d %H:%M:%S") + f".{int(record.msecs):03d}"

    def format(self, record):
        base = f"{self.formatTime(record)} [{record.levelname:<7}] {record.name}: {record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


class JsonFormatter(logging.Formatter):
    def __init__(self, fields: tuple[str, ...] = ("time", "level", "name", "message")):
        super().__init__()
        self._fields = fields

    def format(self, record):
        obj = {
            "time": datetime.fromtimestamp(record.created).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            obj["exc_info"] = self.formatException(record.exc_info)
        # Restrict to requested fields if provided
        if self._fields:
            obj = {k: obj.get(k) for k in self._fields if k in obj}
        return json.dumps(obj, ensure_ascii=False)


# -------------------------
# Setup helpers
# -------------------------

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger (without side-effecting global config)."""
    return logging.getLogger(name or "victurus")


def setup(opts: Optional[LogSetup] = None) -> logging.Logger:
    """
    Configure root logger. Safe to call multiple times (idempotent-ish).
    Returns the root logger.
    """
    if opts is None:
        # Defaults + env overrides
        level_name = os.getenv("VICTURUS_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        as_json = os.getenv("VICTURUS_LOG_JSON", "0").strip().lower() in ("1", "true", "yes", "on")
        log_file = os.getenv("VICTURUS_LOG_FILE", "").strip() or None
        rotate_by_size = os.getenv("VICTURUS_LOG_ROTATE", "size").strip().lower() != "time"
        try:
            max_bytes = int(os.getenv("VICTURUS_LOG_MAX_BYTES", "5000000"))
        except Exception:
            max_bytes = 5_000_000
        try:
            backup_count = int(os.getenv("VICTURUS_LOG_BACKUP", "3"))
        except Exception:
            backup_count = 3
        opts = LogSetup(
            level=level,
            to_console=True,
            log_file=log_file,
            rotate_by_size=rotate_by_size,
            max_bytes=max_bytes,
            backup_count=backup_count,
            as_json=as_json,
        )

    logger = logging.getLogger()
    logger.setLevel(opts.level)

    # Avoid duplicate handlers if setup() is called again
    if not getattr(logger, "_victurus_configured", False):
        # Handlers
        fmt = JsonFormatter() if opts.as_json else PlainFormatter()

        if opts.to_console:
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(opts.level)
            ch.setFormatter(fmt)
            logger.addHandler(ch)

        if opts.log_file:
            if opts.rotate_by_size:
                fh = logging.handlers.RotatingFileHandler(
                    opts.log_file, maxBytes=opts.max_bytes, backupCount=opts.backup_count, encoding="utf-8"
                )
            else:
                # Rotate daily at midnight, keep a few backups
                fh = logging.handlers.TimedRotatingFileHandler(
                    opts.log_file, when="midnight", backupCount=opts.backup_count, encoding="utf-8", utc=False
                )
            fh.setLevel(opts.level)
            fh.setFormatter(fmt)
            logger.addHandler(fh)

        logger._victurus_configured = True  # type: ignore[attr-defined]

    return logger


def install_global_excepthook(logger: Optional[logging.Logger] = None) -> None:
    """
    Log unhandled exceptions. Useful in early startup and worker processes.
    """
    lg = logger or get_logger("victurus")

    def _excepthook(exc_type, exc_value, exc_tb):
        lg.exception("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = _excepthook


# -------------------------
# Sink helper
# -------------------------

def make_sink(logger: Optional[logging.Logger] = None, level: int = logging.INFO) -> Callable[[str], None]:
    """
    Return a simple sink(msg: str) -> None that writes to logging.
    Handy for UniverseSimulator.enable_debug(..., sink=make_sink(get_logger("sim")))
    """
    lg = logger or get_logger("victurus")

    def _sink(msg: str) -> None:
        try:
            lg.log(level, msg)
        except Exception:
            # Never raise from a sink
            pass

    return _sink
