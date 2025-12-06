# architect_http_api/logging/__init__.py

"""
Logging helpers for the Architect HTTP API.

This module provides a thin wrapper around the shared logging utilities
in ``utils.logging_setup`` so that API code can simply do:

    from architect_http_api.logging import get_logger, init_logging

and remain decoupled from the concrete location of the logging setup.
"""

from __future__ import annotations

import logging
from typing import Optional

from utils.logging_setup import init_logging as _core_init_logging
from utils.logging_setup import get_logger as _core_get_logger


DEFAULT_LOGGER_NAME = "architect_http_api"


def init_logging(
    level: Optional[int] = None,
    log_to_file: bool = False,
    filename: Optional[str] = None,
    *,
    force: bool = False,
) -> None:
    """
    Initialize logging for the Architect HTTP API service.

    This delegates to ``utils.logging_setup.init_logging`` and accepts
    the same parameters. Environment variables such as ``AW_LOG_LEVEL``
    and ``AW_LOG_FILE`` are honored by the underlying helper.

    Args:
        level:
            Logging level (e.g. ``logging.DEBUG``). If ``None``, the
            value is read from the ``AW_LOG_LEVEL`` environment variable
            and defaults to ``logging.INFO``.
        log_to_file:
            If ``True``, log to a file (see ``filename``). If ``False``,
            log only to stderr unless ``AW_LOG_FILE`` is set.
        filename:
            Path to the log file. If ``None`` and ``log_to_file`` is
            ``True``, a default such as ``abstract_wiki.log`` may be
            used by the underlying helper.
        force:
            If ``True``, reconfigure logging even if it was already
            initialized.
    """
    _core_init_logging(
        level=level,
        log_to_file=log_to_file,
        filename=filename,
        force=force,
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger for the Architect HTTP API.

    If ``name`` is omitted, a service-level default name is used
    (``architect_http_api``). Otherwise the given name is used as-is.

    This ensures logging has been initialized (calling ``init_logging``
    with default parameters if needed) before returning a logger.
    """
    return _core_get_logger(name or DEFAULT_LOGGER_NAME)


__all__ = ["init_logging", "get_logger", "DEFAULT_LOGGER_NAME"]
