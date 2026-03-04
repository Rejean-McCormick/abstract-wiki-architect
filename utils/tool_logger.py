# C:\MyCode\SemantiK_Architect\Semantik_architect\utils\tool_logger.py
"""
utils/tool_logger.py
--------------------

A small, GUI-friendly stdout logger for SemantiK Architect tools.

Design goals
- Always write to STDOUT (so the GUI console sees progress as normal output).
- Standardize: header / stage / summary / finish.
- Preserve compatibility for external grep/CI by keeping prefixes:
  - "Error:" and "Warning:" at the START of the line.
- Provide a minimal "logging-like" API used across tools:
  - info(), warning(), error(fatal=True), exception(fatal=True)
  - header(), stage(), summary(), start(), finish()

Typical usage
    from utils.tool_logger import ToolLogger
    log = ToolLogger(__file__)
    log.header({"Language": "en"})
    log.stage("Scan", "Found 12 files")
    log.info("Processing %s", "foo.json")
    log.warning("Something looks odd: %s", details)
    log.error("Hard failure: %s", err, fatal=True)
"""

from __future__ import annotations

import datetime as _dt
import logging as _logging
import os as _os
import sys as _sys
import time as _time
import traceback as _traceback
import uuid as _uuid
from typing import Any, Mapping, Optional


def _tool_name_from_hint(hint: str) -> str:
    """
    Convert a path or arbitrary string to a stable tool name.
    Examples:
      "/repo/utils/dump_lexicon_stats.py" -> "dump_lexicon_stats"
      "refresh_index" -> "refresh_index"
    """
    if not hint:
        return "tool"
    base = _os.path.basename(hint)
    if base.endswith(".py"):
        base = base[:-3]
    return base or "tool"


def _safe_percent_format(msg: Any, args: tuple[Any, ...]) -> str:
    """
    Support logging-style formatting: logger.info("x=%s", x)
    but remain safe if percent formatting doesn't apply.
    """
    if msg is None:
        return ""
    s = str(msg)
    if not args:
        return s
    try:
        return s % args
    except Exception:
        # Fallback: append args in a readable way
        return s + " " + " ".join(str(a) for a in args)


class ToolLogger:
    """
    Minimal stdout logger wrapper with standardized sections for CLI tools.
    """

    def __init__(
        self,
        tool: str,
        *,
        level: Optional[int] = None,
        stream: Any = None,
    ) -> None:
        self.tool: str = _tool_name_from_hint(tool)
        self.run_id: str = _uuid.uuid4().hex[:8]
        self._t0: float = _time.time()
        self._started: bool = False
        self._stream = stream if stream is not None else _sys.stdout

        # Choose level from environment if not explicitly provided
        if level is None:
            env = (_os.getenv("SEMANTIK_TOOL_LOG_LEVEL") or _os.getenv("TOOL_LOG_LEVEL") or "").strip().upper()
            level = getattr(_logging, env, _logging.INFO) if env else _logging.INFO

        # Dedicated logger that NEVER writes to stderr and does NOT rely on root config
        self._logger = _logging.getLogger(f"semantik_tool.{self.tool}.{self.run_id}")
        self._logger.propagate = False
        self._logger.setLevel(level)
        self._logger.handlers.clear()

        handler = _logging.StreamHandler(self._stream)
        handler.setLevel(level)
        handler.setFormatter(_logging.Formatter("%(message)s"))
        self._logger.addHandler(handler)

    # ---------------------------------------------------------------------
    # Basic logging-like methods
    # ---------------------------------------------------------------------
    def info(self, msg: Any = "", *args: Any) -> None:
        self._logger.info(_safe_percent_format(msg, args))

    def debug(self, msg: Any = "", *args: Any) -> None:
        self._logger.debug(_safe_percent_format(msg, args))

    def warning(self, msg: Any = "", *args: Any) -> None:
        # Keep prefix at start of line for compatibility
        self._logger.info(f"Warning: {_safe_percent_format(msg, args)}")

    def error(
        self,
        msg: Any = "",
        *args: Any,
        fatal: bool = False,
        exit_code: int = 1,
    ) -> None:
        # Keep prefix at start of line for compatibility
        self._logger.info(f"Error: {_safe_percent_format(msg, args)}")
        if fatal:
            raise SystemExit(exit_code)

    def exception(
        self,
        msg: Any = "",
        *args: Any,
        fatal: bool = False,
        exit_code: int = 1,
    ) -> None:
        """
        Log an error message + current exception traceback to stdout.
        """
        self._logger.info(f"Error: {_safe_percent_format(msg, args)}")
        tb = _traceback.format_exc().rstrip()
        if tb:
            for line in tb.splitlines():
                self._logger.info(line)
        if fatal:
            raise SystemExit(exit_code)

    # ---------------------------------------------------------------------
    # Standardized structured output
    # ---------------------------------------------------------------------
    def header(self, meta: Optional[Mapping[str, Any]] = None, *, title: Optional[str] = None) -> None:
        """
        Print a standardized run header (id/time + optional metadata).
        """
        if not self._started:
            self._started = True

        now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._logger.info(f"=== {self.tool} ===")
        if title:
            self._logger.info(f"Run: {title}")
        self._logger.info(f"Run ID: {self.run_id}")
        self._logger.info(f"Start: {now}")

        if meta:
            for k, v in meta.items():
                self._logger.info(f"{k}: {v}")

        self._logger.info("")  # spacer

    def start(self, title: Optional[str] = None, meta: Optional[Mapping[str, Any]] = None) -> None:
        """
        Alias for header() (some scripts call start()).
        """
        self.header(meta, title=title)

    def stage(self, name: str, message: Optional[str] = None, meta: Optional[Mapping[str, Any]] = None) -> None:
        """
        Print a standardized stage marker.
        """
        self._logger.info(f"--- {name} ---")
        if message:
            self._logger.info(str(message))
        if meta:
            for k, v in meta.items():
                self._logger.info(f"{k}: {v}")
        self._logger.info("")  # spacer

    def summary(
        self,
        data: Optional[Mapping[str, Any]] = None,
        *,
        success: Optional[bool] = None,
        message: Optional[str] = None,
    ) -> None:
        """
        Print a standardized summary block.
        """
        self._logger.info("=== SUMMARY ===")
        if message:
            self._logger.info(str(message))
        if data:
            for k, v in data.items():
                self._logger.info(f"{k}: {v}")
        if success is not None:
            self._logger.info(f"Result: {'SUCCESS' if success else 'FAILURE'}")
        self._logger.info("")  # spacer

    def finish(
        self,
        message: Optional[str] = None,
        *,
        success: Optional[bool] = None,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """
        Print a standardized finish block (duration + optional details).
        """
        dt = _time.time() - self._t0
        status = "SUCCESS" if success is True else "FAILURE" if success is False else "DONE"
        self._logger.info(f"=== FINISH ({status}) in {dt:.2f}s ===")
        if message:
            self._logger.info(str(message))
        if details:
            for k, v in details.items():
                self._logger.info(f"{k}: {v}")
        self._logger.info("")  # spacer

    # ---------------------------------------------------------------------
    # Convenience / compatibility
    # ---------------------------------------------------------------------
    @property
    def logger(self) -> _logging.Logger:
        """
        Underlying stdlib logger (for advanced use).
        """
        return self._logger