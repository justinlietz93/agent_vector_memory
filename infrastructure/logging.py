from __future__ import annotations

import logging
import os


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        level = os.getenv("VM_LOG_LEVEL", "INFO").upper()
        logging.basicConfig(level=getattr(logging, level, logging.INFO), format="%(levelname)s | %(message)s")
    return logger
