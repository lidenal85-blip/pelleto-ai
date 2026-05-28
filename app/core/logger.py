"""
app/core/logger.py — Structured JSON logger.
Usage: from app.core.logger import get_logger; log = get_logger(__name__)
"""
import logging
import json
import os
import sys
from datetime import datetime, timezone
from app.core import config


class JSONFormatter(logging.Formatter):
    SCRUB = {"password", "master_key", "api_key", "authorization", "token", "secret"}

    def format(self, record: logging.LogRecord) -> str:
        d = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k.startswith("_") or k in (
                "name","msg","args","levelname","levelno","pathname",
                "filename","module","exc_info","exc_text","stack_info",
                "lineno","funcName","created","msecs","relativeCreated",
                "thread","threadName","processName","process","message",
            ):
                continue
            d[k] = "***" if k.lower() in self.SCRUB else v
        if record.exc_info:
            d["exception"] = self.formatException(record.exc_info)
        return json.dumps(d, ensure_ascii=False, default=str)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"pelleto.{name}")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)
    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(JSONFormatter())
    logger.addHandler(ch)
    # File
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    fh = logging.FileHandler(os.path.join(config.LOGS_DIR, "pelleto.log"), encoding="utf-8")
    fh.setFormatter(JSONFormatter())
    logger.addHandler(fh)
    logger.propagate = False
    return logger