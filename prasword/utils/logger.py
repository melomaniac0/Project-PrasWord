"""
prasword.utils.logger
=====================
Centralised logging configuration for PrasWord.

All modules obtain their logger via ``get_logger(__name__)``.
The root "prasword" logger is configured once (lazily on first call) to
write to both the console and a rotating file in the user's config directory.

Log level is controlled by the ``PRASWORD_LOG_LEVEL`` environment variable
(default: ``INFO``).  Set to ``DEBUG`` during development.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

_configured: bool = False
_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _configure_root_logger() -> None:
    """One-time configuration of the 'prasword' root logger."""
    global _configured
    if _configured:
        return
    _configured = True

    level_name = os.environ.get("PRASWORD_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger("prasword")
    root.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler.
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # Rotating file handler — stored next to the user's config file.
    try:
        log_dir = Path.home() / ".prasword" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "prasword.log",
            maxBytes=2 * 1024 * 1024,  # 2 MB per file
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # If we can't create the log file (permissions, read-only FS, etc.)
        # just continue with console logging only.
        pass


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger under the 'prasword' hierarchy.

    Parameters
    ----------
    name : str
        Typically ``__name__`` of the calling module.

    Returns
    -------
    logging.Logger
    """
    _configure_root_logger()
    return logging.getLogger(name)
