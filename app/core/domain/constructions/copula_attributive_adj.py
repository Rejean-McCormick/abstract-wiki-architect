# app\core\domain\constructions\copula_attributive_adj.py
# constructions\copula_attributive_adj.py
# constructions/copula_attributive_adj.py

"""
COPULA ATTRIBUTIVE ADJECTIVE CONSTRUCTION
----------------------------------------

This module implements the COPULA_ATTRIBUTIVE_ADJ construction, i.e.
sentences of the form:

    "X is ADJECTIVE"

Examples:
    "Marie Curie is Polish."
    "The experiment is successful."
    "The sky is blue."

The construction is *language-family agnostic*. It delegates all morphology
and language-specific details to a MorphologyAPI and an optional language
profile.

Core idea:
    1. Build a SUBJECT NP (usually the entity being described).
    2. Build an ADJECTIVAL PREDICATE (adjective in predicative form).
    3. Optionally build a COPULA (overt or zero).
    4. Linearize according to a language-profile template.

This module does not know about gender, case systems, agreement rules, etc.
Those are expressed as feature bundles and passed to `morph_api`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol


__all__ = [
    "MorphologyAPI",
    "AttributiveAdjSlots",
    "realize_attributive_adj",
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
            role: Logical role in the clause (e.g. 'subject', 'predicate_adj').
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
class AttributiveAdjSlots:
    """
    Input slots for the COPULA_ATTRIBUTIVE_ADJ construction.

    Required:
        subject_name: Surface string for the subject name (already lexicalized),
                      e.g. "Marie Curie", "The experiment".
        adj_lemma: Lemma for the adjective, e.g. "Polish", "successful", "blue".

    Optional metadata (used only as features; no fixed semantics here):
        subject_gender: 'male' | 'female' | 'neuter' | 'unknown' | language-specific.
        subject_number: 'sg' | 'pl' | language-specific codes.
        degree: 'positive' | 'comparative' | 'superlative' | etc.

        tense: 'present' | 'past' | 'future' | language-specific.
        polarity: 'affirmative' | 'negative'.
        person: grammatical person of the subject (usually 3).

    All of these are passed through to the MorphologyAPI as-is.
    """

    subject_name: str
    adj_lemma: str

    subject_gender: str = "unknown"
    subject_number: str = "sg"
    degree: str = "positive"

    tense: str = "present"
    polarity: str = "affirmative"
    person: int = 3

    # Extra arbitrary features that a particular language/engine may want
    extra_subject_features: Dict[str, Any] = field(default_factory=dict)
    extra_adj_features: Dict[str, Any] = field(default_factory=dict)
    extra_copula_features: Dict[str, Any] = field(default_factory=dict)


def _normalize_spaces(text: str) -> str:
    """
    Collapse multiple spaces and strip leading/trailing whitespace.
    """
    return " ".join(text.split())


def realize_attributive_adj(
    slots: AttributiveAdjSlots,
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: MorphologyAPI,
) -> str:
    """
    Realize a COPULA_ATTRIBUTIVE_ADJ sentence.

    Args:
        slots:
            Structured inputs for the construction (subject, adjective, features).
        lang_profile:
            Optional language profile dict. Used for:
                - word order template
                - zero-copula flags
                - any language-specific toggles

            Recognized keys (all optional):
                attributive_adj_template: str
                    Template string containing the placeholders:
                        "{SUBJ}"  -> subject NP
                        "{COP}"   -> copula (may be empty)
                        "{ADJ}"   -> adjective predicate
                    Default: "{SUBJ} {COP} {ADJ}"

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
    # 2. Build ADJECTIVAL PREDICATE
    # ---------------------------------------------------------------------
    adj_features: Dict[str, Any] = {
        "role": "predicate_adj",
        "gender": slots.subject_gender,  # often agrees with subject
        "number": slots.subject_number,  # often agrees with subject
        "degree": slots.degree,
    }
    adj_features.update(slots.extra_adj_features)

    # Many engines can reuse the same NP realization pathway for adjectives
    # in predicative position, distinguished only by the 'role' and features.
    adj_pred = morph_api.realize_np(
        role="predicate_adj",
        lemma=slots.adj_lemma,
        features=adj_features,
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
        "attributive_adj_template",
        "{SUBJ} {COP} {ADJ}",
    )

    sentence = template.format(
        SUBJ=subject_np,
        COP=copula,
        ADJ=adj_pred,
    )

    return _normalize_spaces(sentence)