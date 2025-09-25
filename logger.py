import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "")  # If set, logs will also be written to this file


def setup_logging() -> logging.Logger:
    """Configure root logger once and return it."""
    root = logging.getLogger()
    if root.handlers:
        return root  # Already configured

    level = getattr(logging, LOG_LEVEL, logging.INFO)
    root.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if LOG_FILE:
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=2)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    return root


def get_logger(name: str) -> logging.Logger:
    """Get a module-level logger with common configuration."""
    if not logging.getLogger().handlers:
        setup_logging()
    return logging.getLogger(name)
