"""
app/adapters/persistence/lexicon/config.py
-----------------

Configuration knobs for the lexicon subsystem.

This module centralizes tunable parameters related to lexicon loading,
validation, normalization, indexing, and caching. Settings can be adjusted from:

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

Enterprise-grade controls:
- AW_LEXICON_STRICT_SCHEMA
    If true, schema errors should be treated as fatal by loaders.
    Default: false

- AW_LEXICON_VALIDATE_ON_LOAD
    If true, loaders should validate each JSON file before merging.
    Default: false

- AW_LEXICON_NORMALIZE_KEYS
    If true, loaders may normalize surface keys (casefold/punct/space) for robust lookup.
    Default: false (preserve legacy keys)

- AW_LEXICON_LOG_COLLISIONS
    If true, loaders may log per-key collisions when merging.
    Default: false

- AW_LEXICON_SCHEMA_STRICT
    Alias of AW_LEXICON_STRICT_SCHEMA (kept for compatibility with older branches).

- AW_LEXICON_LOG_LEVEL
    Override lexicon logger level (DEBUG/INFO/WARNING/ERROR/CRITICAL).
    Default: "" (do not override)

Cache controls:
- AW_LEXICON_CACHE_ENABLED
    If false, applications may choose to bypass caching behavior.
    Default: true

- AW_LEXICON_CACHE_MAX_LANGS
    Soft limit on number of cached language indices (0 = unlimited).
    Default: 0

Notes
=====
- This module does not enforce behavior; it exposes preferences.
- Callers (loader/cache/bootstrap) decide how to apply them.
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


def _clean_dir(value: str, *, default: str = "data/lexicon") -> str:
    """
    Normalize a directory path string without forcing existence.
    Keeps it as a string for compatibility with existing callers.
    """
    s = (value or "").strip()
    if not s:
        s = default
    expanded = os.path.expandvars(os.path.expanduser(s))
    try:
        return str(Path(expanded))
    except Exception:
        return expanded


# ---------------------------------------------------------------------------
# Config object
# ---------------------------------------------------------------------------


@dataclass(slots=True)
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
            languages at startup.

        validate_on_load:
            If True, code that loads lexicon JSON may choose to validate each
            file's structure before merging.
        strict_schema:
            If True, schema errors should be treated as fatal by loaders.

        normalize_keys:
            If True, loaders may normalize output keys (for lookup robustness).
            Default False to preserve legacy behavior.
        log_collisions:
            If True, loaders may log key collisions when merging.

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

    validate_on_load: bool = False
    strict_schema: bool = False

    normalize_keys: bool = False
    log_collisions: bool = False

    log_level: str = ""
    cache_enabled: bool = True
    cache_max_langs: int = 0

    @classmethod
    def from_env(cls) -> "LexiconConfig":
        """
        Build a LexiconConfig instance using environment variables as overrides.
        """
        # [FIX] Use string literal default "data/lexicon" to avoid accessing slot descriptor on class
        lex_dir = _clean_dir(os.getenv("AW_LEXICON_DIR"), default="data/lexicon")

        max_lemmas = _parse_int(
            os.getenv("AW_LEXICON_MAX_LEMMAS", ""),
            0,  # [FIX] Use literal 0
            min_value=0,
        )

        eager = _parse_bool(
            os.getenv("AW_LEXICON_EAGER_LOAD", ""),
            False,  # [FIX] Use literal False
        )

        # Compatibility: allow both AW_LEXICON_STRICT_SCHEMA and AW_LEXICON_SCHEMA_STRICT
        strict_schema = _parse_bool(
            os.getenv("AW_LEXICON_STRICT_SCHEMA", os.getenv("AW_LEXICON_SCHEMA_STRICT", "")),
            False,
        )

        validate_on_load = _parse_bool(
            os.getenv("AW_LEXICON_VALIDATE_ON_LOAD", ""),
            False,
        )

        normalize_keys = _parse_bool(
            os.getenv("AW_LEXICON_NORMALIZE_KEYS", ""),
            False,
        )

        log_collisions = _parse_bool(
            os.getenv("AW_LEXICON_LOG_COLLISIONS", ""),
            False,
        )

        log_level = _parse_log_level(os.getenv("AW_LEXICON_LOG_LEVEL", ""))

        cache_enabled = _parse_bool(
            os.getenv("AW_LEXICON_CACHE_ENABLED", ""),
            True,  # Default True
        )

        cache_max_langs = _parse_int(
            os.getenv("AW_LEXICON_CACHE_MAX_LANGS", ""),
            0,
            min_value=0,
        )

        return cls(
            lexicon_dir=lex_dir,
            max_lemmas_per_language=max_lemmas,
            eager_load=eager,
            validate_on_load=validate_on_load,
            strict_schema=strict_schema,
            normalize_keys=normalize_keys,
            log_collisions=log_collisions,
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

    def resolved_cache_max_langs(self) -> int:
        """
        Return a safe cache_max_langs (non-negative int).
        """
        return max(0, int(self.cache_max_langs or 0))


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