# architect_http_api/logging/config.py

"""
Configuration helpers for logging in the Architect HTTP API service.

This module provides a tiny convenience layer around the generic logging
utilities exposed in ``architect_http_api.logging`` (which in turn
delegate to ``utils.logging_setup``).

Typical usage in the API entrypoint (``architect_http_api/main.py``)::

    from architect_http_api.logging.config import configure_logging

    log = configure_logging()

    app = FastAPI(...)
    log.info("Architect HTTP API started")

By centralizing this here, we keep the rest of the codebase free from
direct environment handling and make it easy to adjust logging policy
for the service in one place.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from . import DEFAULT_LOGGER_NAME, get_logger, init_logging

# Environment variable names used to tweak logging for the HTTP API.
# Note: the underlying utils.logging_setup module also honors AW_LOG_LEVEL
# and AW_LOG_FILE; these API-specific variables merely provide overrides.
API_LOG_LEVEL_ENV = "AW_API_LOG_LEVEL"
API_LOG_FILE_ENV = "AW_API_LOG_FILE"


def _parse_level(value: str | None) -> Optional[int]:
    """
    Map a string log level (e.g. 'DEBUG', 'info') to a logging constant.

    Returns None if the value is empty or unrecognized, in which case
    the underlying logging setup uses its own default.
    """
    if not value:
        return None
    name = value.strip().upper()
    return getattr(logging, name, None)


def configure_logging(
    *,
    service_name: str = DEFAULT_LOGGER_NAME,
    force: bool = False,
) -> logging.Logger:
    """
    Initialize logging for the Architect HTTP API and return a service logger.

    This function is intended to be called once at process startup, typically
    from ``architect_http_api.main``. It:

    1. Reads API-specific environment overrides:
       - AW_API_LOG_LEVEL
       - AW_API_LOG_FILE
    2. Delegates to ``init_logging`` from ``architect_http_api.logging``,
       which in turn uses the shared ``utils.logging_setup`` helper.
    3. Returns a logger for ``service_name`` (default: 'architect_http_api').

    Args:
        service_name:
            Name of the main service logger. Using the default keeps log
            lines easy to filter.
        force:
            If True, reconfigure logging even if it was already initialized.

    Returns:
        A configured ``logging.Logger`` instance for the service.
    """
    level_env = os.getenv(API_LOG_LEVEL_ENV)
    file_env = os.getenv(API_LOG_FILE_ENV)

    level: Optional[int] = _parse_level(level_env)
    log_to_file = bool(file_env)

    init_logging(
        level=level,
        log_to_file=log_to_file,
        filename=file_env or None,
        force=force,
    )

    return get_logger(service_name)


__all__ = [
    "API_LOG_LEVEL_ENV",
    "API_LOG_FILE_ENV",
    "configure_logging",
]


