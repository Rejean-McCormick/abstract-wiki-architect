# constructions\copula_equative_classification.py
# constructions/copula_equative_classification.py

"""
COPULA EQUATIVE CLASSIFICATION CONSTRUCTION
-------------------------------------------

This module implements the COPULA_EQUATIVE_CLASSIFICATION construction, i.e.
sentences of the form:

    "X is a Y (class / type)"

Examples:
    "Python is a programming language."
    "Marie Curie is a physicist."
    "The Nile is a river in Africa."

The construction is *language-family agnostic*. It delegates all morphology and
language-specific details to a MorphologyAPI and an optional language profile.

Core idea:
    1. Build a SUBJECT NP (usually the entity being defined).
    2. Build a CLASS NP (the taxonomic class / type).
    3. Optionally build a COPULA (overt or zero).
    4. Linearize according to language-profile template.

This module does not know about gender, case systems, articles, etc. Those are
expressed as feature bundles and passed to `morph_api`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol


__all__ = [
    "MorphologyAPI",
    "EquativeClassificationSlots",
    "realize_equative_classification",
]


class MorphologyAPI(Protocol):
    """
    Minimal protocol that any morphology layer must implement in order to be
    used by this construction.

    A concrete implementation will typically wrap one of your existing
    family engines (Romance, Slavic, Agglutinative, etc.).
    """

    def realize_np(self, role: str, lemma: str, features: Mapping[str, Any]) -> str:
        """
        Realize a noun phrase.

        Args:
            role: Logical role in the clause (e.g. 'subject', 'class').
            lemma: Base form / dictionary form of the head.
            features: Arbitrary feature bundle (gender, number, case,
                      definiteness, etc.), interpreted by the engine.

        Returns:
            Surface string for the NP (without surrounding punctuation).
        """
        ...

    def realize_copula(self, features: Mapping[str, Any]) -> str:
        """
        Realize the copula ("to be") if the language uses an overt copula
        in this context. Languages with zero copula can return ''.

        Args:
            features: Arbitrary feature bundle (tense, person, number,
                      polarity, etc.), interpreted by the engine.

        Returns:
            Surface string for the copula (may be empty).
        """
        ...


@dataclass
class EquativeClassificationSlots:
    """
    Input slots for the COPULA_EQUATIVE_CLASSIFICATION construction.

    Required:
        subject_name: Surface string for the subject name (already lexicalized),
                      e.g. "Python", "Marie Curie".
        class_lemma: Lemma for the taxonomic class, e.g. "programming language",
                     "physicist", "river".

    Optional metadata (used only as features; no fixed semantics here):
        subject_gender: 'male' | 'female' | 'neuter' | 'unknown' | language-specific.
        subject_number: 'sg' | 'pl' | language-specific codes.
        class_number:   'sg' | 'pl' (e.g. "programming language(s)").
        class_definiteness: 'indefinite' | 'definite' | 'bare' | etc.

        tense: 'present' | 'past' | 'future' | language-specific.
        polarity: 'affirmative' | 'negative'.
        person: grammatical person of the subject (usually 3).

    All of these are passed through to the MorphologyAPI as-is.
    """

    subject_name: str
    class_lemma: str

    subject_gender: str = "unknown"
    subject_number: str = "sg"
    class_number: str = "sg"
    class_definiteness: str = "indefinite"

    tense: str = "present"
    polarity: str = "affirmative"
    person: int = 3

    # Extra arbitrary features that a particular language/engine may want
    extra_subject_features: Dict[str, Any] = field(default_factory=dict)
    extra_class_features: Dict[str, Any] = field(default_factory=dict)
    extra_copula_features: Dict[str, Any] = field(default_factory=dict)


def _normalize_spaces(text: str) -> str:
    """
    Collapse multiple spaces and strip leading/trailing whitespace.
    """
    return " ".join(text.split())


def realize_equative_classification(
    slots: EquativeClassificationSlots,
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: MorphologyAPI,
) -> str:
    """
    Realize a COPULA_EQUATIVE_CLASSIFICATION sentence.

    Args:
        slots:
            Structured inputs for the construction (subject, class, features).
        lang_profile:
            Optional language profile dict. Used for:
                - word order template
                - zero-copula flags
                - any language-specific toggles

            Recognized keys (all optional):
                classification_template: str
                    Template string containing the placeholders:
                        "{SUBJ}"  -> subject NP
                        "{COP}"   -> copula (may be empty)
                        "{CLASS}" -> class NP
                    Default: "{SUBJ} {COP} {CLASS}"

                enforce_zero_copula: bool
                    If True, skip copula realization and treat it as empty.

        morph_api:
            Implementation of MorphologyAPI that knows how to turn feature
            bundles into surface forms for a specific language.

    Returns:
        A fully realized sentence string (no trailing space, but *without*
        final punctuation, which can be added by a higher layer).
    """
    lang_profile = lang_profile or {}

    # ---------------------------------------------------------------------
    # 1. Build SUBJECT NP
    # ---------------------------------------------------------------------
    subject_features: Dict[str, Any] = {
        "role": "subject",
        "gender": slots.subject_gender,
        "number": slots.subject_number,
        "person": slots.person,
    }
    subject_features.update(slots.extra_subject_features)

    subject_np = morph_api.realize_np(
        role="subject",
        lemma=slots.subject_name,
        features=subject_features,
    )

    # ---------------------------------------------------------------------
    # 2. Build CLASS NP
    # ---------------------------------------------------------------------
    class_features: Dict[str, Any] = {
        "role": "class",
        "number": slots.class_number,
        "definiteness": slots.class_definiteness,
        "gender": slots.subject_gender,  # often agrees with subject for professions
    }
    class_features.update(slots.extra_class_features)

    class_np = morph_api.realize_np(
        role="class",
        lemma=slots.class_lemma,
        features=class_features,
    )

    # ---------------------------------------------------------------------
    # 3. Build COPULA (possibly empty)
    # ---------------------------------------------------------------------
    if bool(lang_profile.get("enforce_zero_copula", False)):
        copula = ""
    else:
        copula_features: Dict[str, Any] = {
            "tense": slots.tense,
            "polarity": slots.polarity,
            "person": slots.person,
            "number": slots.subject_number,
        }
        copula_features.update(slots.extra_copula_features)
        copula = morph_api.realize_copula(copula_features)

    # ---------------------------------------------------------------------
    # 4. Linearization with template
    # ---------------------------------------------------------------------
    template: str = lang_profile.get(
        "classification_template",
        "{SUBJ} {COP} {CLASS}",
    )

    sentence = template.format(
        SUBJ=subject_np,
        COP=copula,
        CLASS=class_np,
    )

    return _normalize_spaces(sentence)