"""Logging setup for the Polymarket Stop-Loss Bot."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

_logger: Optional[logging.Logger] = None


def get_logger(name: str = "polymarket_bot") -> logging.Logger:
    """Get or create the bot logger with file and console handlers."""
    global _logger

    if _logger is not None:
        return _logger

    # Import here to avoid circular imports
    from bot.config import load_config

    config = load_config()
    log_config = config.get("logging", {})

    level = getattr(logging, log_config.get("level", "INFO").upper())
    log_file = log_config.get("file", "logs/bot.log")
    max_size = log_config.get("max_size_mb", 10) * 1024 * 1024
    backup_count = log_config.get("backup_count", 5)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Create logs directory if needed
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # Format
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_size,
        backupCount=backup_count,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _logger = logger
    return logger
