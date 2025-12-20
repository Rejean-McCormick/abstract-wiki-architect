# app\adapters\persistence\lexicon\errors.py
# lexicon\errors.py
"""
lexicon/errors.py
-----------------

Custom exception types for the lexicon subsystem.

These are intentionally small and descriptive so that callers can
distinguish between:

    - configuration / loading problems
    - missing lexicon data
    - unexpected schema issues

Typical usage:

    from lexicon.errors import (
        LexiconError,
        LexiconNotFound,
        LexemeNotFound,
        LexiconSchemaError,
        LexiconConfigError,
    )

    try:
        lemmas = load_lexicon("fr")
    except LexiconNotFound as e:
        log.error("No lexicon for 'fr': %s", e)
    except LexiconSchemaError as e:
        log.error("Bad lexicon schema: %s", e)
"""

from __future__ import annotations


class LexiconError(Exception):
    """
    Base class for all lexicon-related errors.

    Catch this if you want to handle any lexicon problem in a single
    place; catch subclasses for more fine-grained handling.
    """


class LexiconNotFound(LexiconError):
    """
    Raised when no lexicon can be located for a requested language.

    Typically thrown by:
        - lexicon.loader.load_lexicon(lang_code)
    """

    def __init__(self, language: str, message: str | None = None) -> None:
        if message is None:
            message = f"Lexicon for language '{language}' not found."
        super().__init__(message)
        self.language = language


class LexiconSchemaError(LexiconError):
    """
    Raised when a lexicon JSON file does not match the expected schema.

    Examples:
        - Missing required keys
        - Wrong types for critical fields
    """

    def __init__(self, path: str, detail: str | None = None) -> None:
        msg = f"Invalid lexicon schema in '{path}'."
        if detail:
            msg += f" Detail: {detail}"
        super().__init__(msg)
        self.path = path
        self.detail = detail


class LexemeNotFound(LexiconError):
    """
    Raised when a specific lexeme (by key, lemma, or ID) cannot be found
    in an otherwise valid lexicon.

    Typically thrown by index / look-up helpers.
    """

    def __init__(self, language: str, key: str, pos: str | None = None) -> None:
        if pos:
            message = (
                f"Lexeme '{key}' (pos={pos}) not found in lexicon for '{language}'."
            )
        else:
            message = f"Lexeme '{key}' not found in lexicon for '{language}'."
        super().__init__(message)
        self.language = language
        self.key = key
        self.pos = pos


class LexiconConfigError(LexiconError):
    """
    Raised for configuration problems related to lexicon loading:
        - unknown lexicon source
        - conflicting configuration options
        - missing paths, etc.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


__all__ = [
    "LexiconError",
    "LexiconNotFound",
    "LexiconSchemaError",
    "LexemeNotFound",
    "LexiconConfigError",
]
