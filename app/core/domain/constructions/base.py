# constructions\base.py
# constructions/base.py

"""
Base abstractions for clause-level constructions.

This module defines lightweight, language-agnostic interfaces for
"constructions" – reusable clause templates such as:

- COPULA_EQUATIVE_SIMPLE
- COPULA_LOCATIVE
- TRANSITIVE_EVENT
- RELATIVE_CLAUSE_SUBJECT_GAP
- etc.

Each concrete construction module (e.g. constructions/copula_equative_simple.py)
implements one Construction subclass and uses a MorphologyAPI to obtain
inflected word forms. The construction itself is responsible only for:

- choosing which arguments (SUBJ, PRED, TOPIC, etc.) to use,
- deciding word order and local function words (like "and", "that"),
- returning a sequence of surface tokens and the joined text.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, Optional


__all__ = [
    "ClauseInput",
    "ClauseOutput",
    "MorphologyAPI",
    "Construction",
    "get_role",
    "bool_feature",
    "str_feature",
]


# ---------------------------------------------------------------------------
# Types for abstract inputs / outputs
# ---------------------------------------------------------------------------


@dataclass
class ClauseInput:
    """
    Language-independent abstract input for a construction.

    `roles` is a free-form mapping from role labels to values, for example:

      roles = {
        "SUBJ": {"lemma": "Marie Curie", "pos": "PROPN"},
        "PRED_NP": {"lemma": "physicist", "pos": "NOUN"},
        "NATIONALITY_ADJ": {"lemma": "Polish", "pos": "ADJ"},
      }

    `features` is a bag of global features (tense, polarity, information structure),
    e.g.:

      features = {
        "tense": "past",
        "polarity": "affirmative",
        "topic": "SUBJ",
      }
    """

    roles: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClauseOutput:
    """
    Surface-level result of realizing a construction.

    - `tokens`: the token sequence (already ordered).
    - `text`: the final string after token joining (e.g. with spaces / language-specific rules).
    - `metadata`: optional extra info (focus positions, alignment between tokens and roles, etc.).
    """

    tokens: List[str] = field(default_factory=list)
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Morphology interface
# ---------------------------------------------------------------------------


class MorphologyAPI(Protocol):
    """
    Minimal protocol that construction modules can rely on to obtain inflected forms.

    Concrete implementations will typically wrap family-specific engines
    (romance, slavic, etc.) plus per-language JSON configs.

    The intention is that constructions never need to know *how* inflection
    is implemented – they just request forms by lemma + POS + feature bundle.
    """

    def realize_lexeme(
        self,
        lemma: str,
        pos: str,
        features: Dict[str, Any],
    ) -> str:
        """
        Return a single inflected word form (no spaces).

        Example call:
            realize_lexeme(
                lemma="physicist",
                pos="NOUN",
                features={"case": "nominative", "number": "sg", "gender": "female"}
            )
        """
        ...

    def join_tokens(self, tokens: List[str]) -> str:
        """
        Join a list of tokens into surface text, applying any
        language-specific spacing or orthographic rules.

        Default implementations can simply do " ".join(tokens), but
        languages with clitics or special spacing may override this.
        """
        ...


# ---------------------------------------------------------------------------
# Base Construction class
# ---------------------------------------------------------------------------


class Construction(ABC):
    """
    Abstract base class for all constructions.

    Each concrete subclass should:

    - declare a stable `id` string (e.g. "COPULA_EQUATIVE_SIMPLE"),
    - implement `realize_clause` to produce a ClauseOutput.

    Constructions should be *pure* in the sense that they do not perform
    I/O or global config lookup; everything needed should be passed in via:

    - `abstract` (ClauseInput): semantic / syntactic roles and global features,
    - `lang_profile` (dict): language-level settings (word order, particles, etc.),
    - `morph` (MorphologyAPI): the only way to obtain inflected word forms.
    """

    #: Stable identifier for this construction type.
    id: str = "BASE_CONSTRUCTION"

    @abstractmethod
    def realize_clause(
        self,
        abstract: ClauseInput,
        lang_profile: Dict[str, Any],
        morph: MorphologyAPI,
    ) -> ClauseOutput:
        """
        Realize a clause for this construction.

        Implementations will typically:

        1. Extract relevant roles from `abstract.roles`.
        2. Decide which lemmas + POS + feature bundles to send to `morph`.
        3. Build an ordered list of tokens.
        4. Use `morph.join_tokens` to get the final `text`.
        5. Optionally fill `metadata` with alignment info.

        They MUST NOT mutate `abstract`, `lang_profile`, or `morph`.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def get_role(
    abstract: ClauseInput,
    role: str,
    default: Optional[Any] = None,
) -> Any:
    """
    Safe accessor for a role inside ClauseInput.

    Example:
        subj = get_role(abstract, "SUBJ")
        pred = get_role(abstract, "PRED_NP")

    If the role is missing and no default is provided, KeyError is raised.
    """
    if role in abstract.roles:
        return abstract.roles[role]
    if default is not None:
        return default
    raise KeyError(f"Missing role '{role}' in ClauseInput.roles")


def bool_feature(
    abstract: ClauseInput,
    name: str,
    default: bool = False,
) -> bool:
    """
    Convenience accessor for boolean features.

    Example:
        is_negative = bool_feature(abstract, "negative", default=False)
    """
    value = abstract.features.get(name, default)
    return bool(value)


def str_feature(
    abstract: ClauseInput,
    name: str,
    default: str = "",
) -> str:
    """
    Convenience accessor for string features.

    Example:
        tense = str_feature(abstract, "tense", default="present")
    """
    value = abstract.features.get(name, default)
    return str(value) if value is not None else default