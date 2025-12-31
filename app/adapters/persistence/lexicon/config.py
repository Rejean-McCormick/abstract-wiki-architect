# app/adapters/persistence/lexicon/config.py
# lexicon/config.py
"""
lexicon/config.py
-----------------

Configuration knobs for the lexicon subsystem.

This module centralizes tunable parameters related to lexicon loading,
validation, indexing, and caching. Settings can be adjusted from:

- application code (via set_config / direct mutation), or
- environment variables.

Environment variables
=====================

Core:
- AW_LEXICON_DIR
    Base directory for lexicon JSON files.
    Default: "data/lexicon"

- AW_LEXICON_MAX_LEMMAS
    Soft limit on the number of surface forms/lemmas loaded per language.
    0 means "no limit".
    Default: 0

- AW_LEXICON_EAGER_LOAD
    If "1"/"true"/"yes"/"on", applications may choose to eagerly load
    lexicons for frequently-used languages at startup.
    Default: false

Enterprise-grade controls (optional):
- AW_LEXICON_STRICT_SCHEMA
    If true, loaders/bootstrappers may choose to fail hard on schema errors.
    Default: false

- AW_LEXICON_VALIDATE_ON_LOAD
    If true, validate each JSON file before merging.
    Default: false

- AW_LEXICON_LOG_LEVEL
    Override lexicon logger level (DEBUG/INFO/WARNING/ERROR/CRITICAL).
    Default: "" (do not override)

- AW_LEXICON_CACHE_ENABLED
    If false, callers may bypass/disable caching behavior (best-effort; the
    cache module remains in-memory and can still be used explicitly).
    Default: true

- AW_LEXICON_CACHE_MAX_LANGS
    Soft limit on number of cached language indices (0 = unlimited).
    Default: 0

Typical usage
=============

    from lexicon.config import get_config

    cfg = get_config()
    print(cfg.lexicon_dir)

    # Adjust at runtime (e.g. in tests)
    cfg.lexicon_dir = "tests/data/lexicon"
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


_TRUE_SET = {"1", "true", "yes", "y", "on", "t"}
_FALSE_SET = {"0", "false", "no", "n", "off", "f"}


def _parse_bool(raw: str, default: bool) -> bool:
    s = (raw or "").strip().lower()
    if not s:
        return default
    if s in _TRUE_SET:
        return True
    if s in _FALSE_SET:
        return False
    return default


def _parse_int(raw: str, default: int, *, min_value: int = 0) -> int:
    s = (raw or "").strip()
    if not s:
        return default
    try:
        value = int(s)
    except ValueError:
        return default
    if value < min_value:
        return min_value
    return value


def _parse_log_level(raw: str) -> str:
    s = (raw or "").strip().upper()
    if not s:
        return ""
    allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    return s if s in allowed else ""


def _clean_dir(value: str) -> str:
    """
    Normalize a directory path string without forcing existence.
    Keeps it as a string for compatibility with existing callers.
    """
    s = (value or "").strip()
    if not s:
        return "data/lexicon"
    # Expand ~ and env vars; normalize separators.
    expanded = os.path.expandvars(os.path.expanduser(s))
    try:
        return str(Path(expanded))
    except Exception:
        return expanded


# ---------------------------------------------------------------------------
# Config object
# ---------------------------------------------------------------------------


@dataclass
class LexiconConfig:
    """
    Configuration values for the lexicon subsystem.

    Fields:
        lexicon_dir:
            Base directory where per-language lexicon JSON files live.
        max_lemmas_per_language:
            Soft limit on the number of surface forms loaded per language.
            0 means "no limit".
        eager_load:
            If True, applications may choose to preload lexicons for common
            languages at startup. This module does not enforce eager loading.

        strict_schema:
            If True, code that loads lexicon JSON may choose to fail on schema
            validation errors (rather than warn and continue).

        validate_on_load:
            If True, code that loads lexicon JSON may choose to validate each
            file's structure before merging.

        log_level:
            Optional logger level override for lexicon subsystem components.

        cache_enabled:
            If False, applications may choose to avoid using the cache module.

        cache_max_langs:
            Soft limit on the number of cached language indices. 0 means unlimited.
    """

    lexicon_dir: str = "data/lexicon"
    max_lemmas_per_language: int = 0
    eager_load: bool = False

    strict_schema: bool = False
    validate_on_load: bool = False

    log_level: str = ""
    cache_enabled: bool = True
    cache_max_langs: int = 0

    @classmethod
    def from_env(cls) -> "LexiconConfig":
        """
        Build a LexiconConfig instance using environment variables as overrides.
        """
        lex_dir = _clean_dir(os.getenv("AW_LEXICON_DIR", cls.lexicon_dir))

        max_lemmas = _parse_int(
            os.getenv("AW_LEXICON_MAX_LEMMAS", ""),
            cls.max_lemmas_per_language,
            min_value=0,
        )

        eager = _parse_bool(
            os.getenv("AW_LEXICON_EAGER_LOAD", ""),
            cls.eager_load,
        )

        strict_schema = _parse_bool(
            os.getenv("AW_LEXICON_STRICT_SCHEMA", ""),
            cls.strict_schema,
        )

        validate_on_load = _parse_bool(
            os.getenv("AW_LEXICON_VALIDATE_ON_LOAD", ""),
            cls.validate_on_load,
        )

        log_level = _parse_log_level(os.getenv("AW_LEXICON_LOG_LEVEL", ""))

        cache_enabled = _parse_bool(
            os.getenv("AW_LEXICON_CACHE_ENABLED", ""),
            cls.cache_enabled,
        )

        cache_max_langs = _parse_int(
            os.getenv("AW_LEXICON_CACHE_MAX_LANGS", ""),
            cls.cache_max_langs,
            min_value=0,
        )

        return cls(
            lexicon_dir=lex_dir,
            max_lemmas_per_language=max_lemmas,
            eager_load=eager,
            strict_schema=strict_schema,
            validate_on_load=validate_on_load,
            log_level=log_level,
            cache_enabled=cache_enabled,
            cache_max_langs=cache_max_langs,
        )

    def resolved_lexicon_dir(self, *, project_root: Optional[Path] = None) -> Path:
        """
        Return an absolute Path for lexicon_dir.

        - Expands ~ and env vars.
        - If lexicon_dir is relative and project_root is provided, resolves against it.
          Otherwise returns a normalized Path (may remain relative).
        """
        base = Path(os.path.expandvars(os.path.expanduser(self.lexicon_dir)))
        if base.is_absolute():
            return base
        if project_root is not None:
            return (project_root / base).resolve()
        return base


# Singleton configuration instance
_CONFIG: Optional[LexiconConfig] = None


def get_config() -> LexiconConfig:
    """
    Return the global LexiconConfig instance, creating it from environment
    variables on first use.
    """
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = LexiconConfig.from_env()
    return _CONFIG


def set_config(config: LexiconConfig) -> None:
    """
    Replace the global LexiconConfig instance.

    Useful for tests and for applications that want to inject config
    from a central settings module.
    """
    global _CONFIG
    if not isinstance(config, LexiconConfig):
        raise TypeError("config must be a LexiconConfig instance")
    _CONFIG = config


__all__ = ["LexiconConfig", "get_config", "set_config"]
