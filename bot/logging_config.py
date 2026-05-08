"""
logging_config.py — Configures a dual-handler logger (file + console).
"""

import logging
import os
from bot.config import LOG_FILE, LOG_LEVEL


def setup_logger(name: str = "trading_bot") -> logging.Logger:
    """
    Returns a configured logger with:
      - FileHandler  → logs/trading.log  (DEBUG and above, detailed format)
      - StreamHandler → stderr            (WARNING and above, minimal format)
    """
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ── File handler ──────────────────────────────────────────────────────────
    file_fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_fmt)

    # ── Console handler ───────────────────────────────────────────────────────
    console_fmt = logging.Formatter(fmt="%(levelname)-8s %(message)s")
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(console_fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


# Module-level singleton used by all bot sub-modules
logger = setup_logger()
