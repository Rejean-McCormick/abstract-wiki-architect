# utils/logging_setup.py
"""
utils/logging_setup.py
----------------------

Shared logging configuration for utility scripts.
"""

import logging
import sys
from typing import Optional

def init_logging(level: int = logging.INFO, format_str: Optional[str] = None) -> None:
    """
    Initialize basic logging configuration to stderr.
    """
    if format_str is None:
        format_str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr
    )

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    """
    return logging.getLogger(name)