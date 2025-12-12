"""
Logging utilities with sane defaults for local dev and production.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

DEFAULT_LOG_DIR = "./"
DEFAULT_LOG_FILE = "app.log"
DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def get_root_logger() -> logging.Logger:
    """Return the process-wide root logger."""
    return logging.getLogger("")


def _build_formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _ensure_handlers(logger: logging.Logger, handlers: list[logging.Handler]) -> None:
    # Avoid duplicate handlers when setup is called multiple times.
    existing = set(logger.handlers)
    for handler in handlers:
        if handler not in existing:
            logger.addHandler(handler)


def setup_logging(
    *,
    log_dir: str = DEFAULT_LOG_DIR,
    log_file: str = DEFAULT_LOG_FILE,
    level: str | int = DEFAULT_LOG_LEVEL,
    truncate: bool = False,
    with_console: bool = True,
) -> logging.Logger:
    """
    Configure application logging with rotating file output and optional console stream.
    Safe to call multiple times; handlers are only added once.
    """

    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, log_file)

    if truncate and os.path.exists(path):
        with open(path, "w", encoding="utf-8"):
            pass

    formatter = _build_formatter()

    file_handler = RotatingFileHandler(
        path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    handlers: list[logging.Handler] = [file_handler]

    if with_console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        handlers.append(console)

    root = get_root_logger()
    root.setLevel(level)
    _ensure_handlers(root, handlers)

    # Propagate to child loggers automatically.
    root.propagate = True
    return root


# Backwards compatibility shim for existing imports.
def setup_file_logging() -> logging.Logger:
    return setup_logging()
