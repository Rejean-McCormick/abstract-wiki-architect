# lexicon\config.py
"""
lexicon/config.py
-----------------

Configuration knobs for the lexicon subsystem.

The goal of this module is to centralize all tunable parameters related
to lexicon loading, indexing, and caching so that they can be adjusted
from:

- application code, or
- environment variables.

This keeps the lexicon code itself simple and avoids sprinkling magic
constants throughout the codebase.

Environment variables
=====================

The following environment variables are recognized:

- AW_LEXICON_DIR
    Override the base directory for lexicon JSON files.
    Default: "data/lexicon"

- AW_LEXICON_MAX_LEMMAS
    Soft limit on the number of lexemes to consider when loading a
    single language. Use this for experiments or memory-constrained
    environments. Default: 0 (no limit).

- AW_LEXICON_EAGER_LOAD
    If set to "1" or "true", some applications may choose to eagerly
    load lexicons for frequently-used languages at startup.
    Default: false (lazy loading).

Typical usage
=============

    from lexicon.config import get_config

    cfg = get_config()
    print(cfg.lexicon_dir)

    # Adjust at runtime (e.g. in tests)
    cfg.lexicon_dir = "tests/data/lexicon"

You normally only need to call `get_config()`; the same singleton
instance is returned each time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LexiconConfig:
    """
    Configuration values for the lexicon subsystem.

    Fields:
        lexicon_dir:
            Base directory where per-language lexicon JSON files live.
        max_lemmas_per_language:
            Soft limit on the number of lexemes loaded per language.
            0 or None means "no limit".
        eager_load:
            If True, applications may choose to preload lexicons for
            common languages at startup. This module does not enforce
            eager loading by itself; it simply exposes the preference.
    """

    lexicon_dir: str = "data/lexicon"
    max_lemmas_per_language: int = 0
    eager_load: bool = False

    @classmethod
    def from_env(cls) -> "LexiconConfig":
        """
        Build a LexiconConfig instance using environment variables as
        overrides on top of sensible defaults.
        """
        lex_dir = os.getenv("AW_LEXICON_DIR", cls.lexicon_dir)

        max_lemmas_raw = os.getenv("AW_LEXICON_MAX_LEMMAS", "").strip()
        if max_lemmas_raw:
            try:
                max_lemmas = int(max_lemmas_raw)
                if max_lemmas < 0:
                    max_lemmas = 0
            except ValueError:
                max_lemmas = cls.max_lemmas_per_language
        else:
            max_lemmas = cls.max_lemmas_per_language

        eager_raw = os.getenv("AW_LEXICON_EAGER_LOAD", "").strip().lower()
        eager = eager_raw in {"1", "true", "yes", "on"}

        return cls(
            lexicon_dir=lex_dir,
            max_lemmas_per_language=max_lemmas,
            eager_load=eager,
        )


# Singleton configuration instance
_CONFIG: Optional[LexiconConfig] = None


def get_config() -> LexiconConfig:
    """
    Return the global LexiconConfig instance, creating it from
    environment variables on first use.
    """
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = LexiconConfig.from_env()
    return _CONFIG


def set_config(config: LexiconConfig) -> None:
    """
    Replace the global LexiconConfig instance.

    This is mainly useful for tests, where you may want to point the
    lexicon directory at a fixture path without touching environment
    variables.
    """
    global _CONFIG
    _CONFIG = config


__all__ = ["LexiconConfig", "get_config", "set_config"]
