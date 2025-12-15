# morphology\base.py
"""
morphology/base.py

Shared abstractions and utilities for all morphology engines.

This module defines:
- A lightweight feature representation (FeatureDict).
- Request / result dataclasses used by constructions and engines.
- An abstract MorphologyEngine interface.
- A simple registry so engines can be created by language family.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Type


# ---------------------------------------------------------------------------
# Basic types
# ---------------------------------------------------------------------------

FeatureDict = Mapping[str, str]
"""A simple mapping of feature name -> feature value.

Examples:
    {"number": "sg", "gender": "f", "tense": "past"}
"""


@dataclass(frozen=True)
class MorphRequest:
    """
    High-level request for an inflected word form.

    Attributes:
        lemma:
            Dictionary form of the word (e.g. "physicien", "be", "discover").
        pos:
            Part of speech tag (e.g. "NOUN", "VERB", "ADJ"). The exact
            tagset is up to the caller, but should be consistent across
            the system.
        features:
            Morphosyntactic features (number, gender, case, tense, etc.).
        language_code:
            ISO language code (e.g. "fr", "tr"). Engines may or may not
            need this, but it is useful for logging and debugging.
    """

    lemma: str
    pos: str
    features: FeatureDict = field(default_factory=dict)
    language_code: Optional[str] = None


@dataclass(frozen=True)
class MorphResult:
    """
    Result of a morphology lookup / inflection.

    Attributes:
        surface:
            The final surface form (e.g. "physicienne", "discovered").
        lemma:
            The lemma used to derive this form. This may differ from the
            original request if the engine had to normalize or redirect
            (e.g. from an alias).
        pos:
            Part of speech of the returned form.
        features:
            The feature bundle that was actually used. Engines may adjust or
            enrich the original request (e.g. defaulting number="sg").
        debug:
            Optional debugging metadata (selected rule ids, irregular hits,
            intermediate forms, etc.). Not required for generation but useful
            for QA and introspection.
    """

    surface: str
    lemma: str
    pos: str
    features: FeatureDict = field(default_factory=dict)
    debug: Mapping[str, Any] = field(default_factory=dict)


class MorphologyError(RuntimeError):
    """Raised when a morphology engine cannot satisfy a given request."""

    pass


# ---------------------------------------------------------------------------
# Abstract engine interface
# ---------------------------------------------------------------------------


class MorphologyEngine(abc.ABC):
    """
    Base class for all morphology engines.

    Engines are typically registered per language *family* (Romance,
    Slavic, Agglutinative, etc.) and parameterised by a per-language
    configuration dictionary.

    Subclasses must implement `inflect()`. They may also add
    family-specific helper methods (e.g. for vowel harmony, case
    selection).
    """

    #: Language family identifier, e.g. "romance", "slavic".
    #: This is populated when the class is registered.
    family: str

    def __init__(self, language_code: str, config: Mapping[str, Any]):
        self.language_code = language_code
        self.config: Mapping[str, Any] = config

    @abc.abstractmethod
    def inflect(self, request: MorphRequest) -> MorphResult:
        """
        Compute an inflected form for the given request.

        Engines should:
            - Respect the lemma, pos, and features as much as possible.
            - Use irregular dictionaries and pattern rules from `self.config`.
            - Raise MorphologyError if they truly cannot produce a form.

        Implementations are free to add engine-specific keys in
        `request.features` and to populate `MorphResult.debug` with rule
        trace information.
        """
        raise NotImplementedError

    # Convenience wrapper -------------------------------------------------

    def inflect_simple(
        self,
        lemma: str,
        pos: str,
        features: Optional[FeatureDict] = None,
    ) -> str:
        """
        Convenience method when only the surface string is needed.

        Example:
            engine.inflect_simple(
                "physicien",
                "NOUN",
                {"number": "sg", "gender": "f"},
            )
        """
        req = MorphRequest(
            lemma=lemma,
            pos=pos,
            features=features or {},
            language_code=self.language_code,
        )
        return self.inflect(req).surface


# ---------------------------------------------------------------------------
# Engine registry and factory
# ---------------------------------------------------------------------------

ENGINE_REGISTRY: Dict[str, Type[MorphologyEngine]] = {}
"""
Global registry mapping language family name -> MorphologyEngine subclass.

Example keys: "romance", "slavic", "agglutinative".
"""


def register_engine(family: str):
    """
    Class decorator to register a MorphologyEngine subclass under a
    family name.

    Usage:

        @register_engine("romance")
        class RomanceMorphology(MorphologyEngine):
            ...

    After registration, `create_engine("romance", "fr", config)` will
    construct the appropriate engine instance.
    """

    def decorator(cls: Type[MorphologyEngine]) -> Type[MorphologyEngine]:
        if not issubclass(cls, MorphologyEngine):
            raise TypeError("Only MorphologyEngine subclasses can be registered")

        if family in ENGINE_REGISTRY:
            raise ValueError(f"Engine already registered for family '{family}'")

        ENGINE_REGISTRY[family] = cls
        # Attach the family attribute for convenience (e.g. for logging).
        cls.family = family  # type: ignore[attr-defined]
        return cls

    return decorator


def create_engine(
    family: str,
    language_code: str,
    config: Mapping[str, Any],
) -> MorphologyEngine:
    """
    Factory function to create a morphology engine for a given family.

    Args:
        family:
            Language family identifier used at registration time.
        language_code:
            ISO language code for this particular instance (e.g. "fr", "tr").
        config:
            Per-language configuration dictionary (suffix rules, irregular
            lexicon, phonological triggers, etc.).

    Returns:
        An instance of the appropriate MorphologyEngine subclass.

    Raises:
        KeyError: if no engine is registered for the given family.
    """
    try:
        cls = ENGINE_REGISTRY[family]
    except KeyError as exc:
        raise KeyError(
            f"No morphology engine registered for family '{family}'"
        ) from exc

    return cls(language_code=language_code, config=config)


def list_registered_families() -> Dict[str, Type[MorphologyEngine]]:
    """
    Return a snapshot of the current engine registry.

    Mainly useful for debugging and introspection.
    """
    return dict(ENGINE_REGISTRY)