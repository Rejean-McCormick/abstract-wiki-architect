# app/core/domain/constructions/intransitive_event.py
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Union

from .base import ClauseInput, ClauseOutput, Construction

SubjectSlot = Union[str, Mapping[str, Any]]
AdverbialSlot = Union[str, Mapping[str, Any]]


class IntransitiveEventConstruction(Construction):
    """
    Runtime construction for intransitive event clauses.

    Canonical runtime ID:
        intransitive_event

    ClauseInput.roles:
        - "subject": SubjectSlot
        - "adverbials": list[AdverbialSlot] | tuple[AdverbialSlot, ...] | AdverbialSlot

    ClauseInput.features:
        - "verb_lemma": str                (required)
        - "tense": str                     (default: "present")
        - "aspect": str                    (default: "simple")
        - "polarity": str                  (default: "positive")
        - "voice": str                     (default: "active")
    """

    id: str = "intransitive_event"

    def realize_clause(
        self,
        abstract: ClauseInput,
        lang_profile: Dict[str, Any],
        morph: Any,
    ) -> ClauseOutput:
        roles = abstract.roles or {}
        features = abstract.features or {}

        subject_surface = self._realize_subject(roles.get("subject"), morph)
        verb_surface = self._realize_verb(features, morph)
        adverb_surfaces = self._realize_adverbials(roles.get("adverbials"), morph)

        basic_word_order = str(lang_profile.get("basic_word_order", "SVO")).upper()
        adv_position = str(
            lang_profile.get("intransitive_adverb_position", "after_verb")
        ).strip().lower()

        tokens = self._linearize(
            subject_surface=subject_surface,
            verb_surface=verb_surface,
            adverb_surfaces=adverb_surfaces,
            basic_word_order=basic_word_order,
            adv_position=adv_position,
        )

        if hasattr(morph, "join_tokens"):
            text = morph.join_tokens(tokens)
        else:
            text = " ".join(tokens)

        return ClauseOutput(
            tokens=tokens,
            text=text,
            metadata={
                "construction_id": self.id,
                "basic_word_order": basic_word_order,
                "adverb_position": adv_position,
            },
        )

    # Compatibility shim for older callers that still pass a flat slots dict
    # and expect a plain string.
    def realize(
        self,
        slots: Dict[str, Any],
        lang_profile: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        abstract = ClauseInput(
            roles={
                "subject": slots.get("subject"),
                "adverbials": slots.get("adverbials", []),
            },
            features={
                "verb_lemma": slots.get("verb_lemma", ""),
                "tense": slots.get("tense", "present"),
                "aspect": slots.get("aspect", "simple"),
                "polarity": slots.get("polarity", "positive"),
                "voice": slots.get("voice", "active"),
            },
        )
        return self.realize_clause(abstract, lang_profile, morph_api).text

    def _linearize(
        self,
        *,
        subject_surface: str,
        verb_surface: str,
        adverb_surfaces: List[str],
        basic_word_order: str,
        adv_position: str,
    ) -> List[str]:
        tokens: List[str] = []

        # V-initial profiles: VSO/VOS -> default VS ordering for intransitives.
        if basic_word_order in {"VSO", "VOS"}:
            if adv_position == "before_verb" and adverb_surfaces:
                tokens.extend(adverb_surfaces)
            if verb_surface:
                tokens.append(verb_surface)
            if subject_surface:
                tokens.append(subject_surface)
            if adv_position in {"after_verb", "sentence_final"} and adverb_surfaces:
                tokens.extend(adverb_surfaces)
            return [t for t in tokens if t]

        # Default fallback for SVO/SOV/OSV/OVS and unknown profiles: SV order.
        if subject_surface:
            tokens.append(subject_surface)

        if adv_position == "before_verb" and adverb_surfaces:
            tokens.extend(adverb_surfaces)

        if verb_surface:
            tokens.append(verb_surface)

        if adv_position in {"after_verb", "sentence_final"} and adverb_surfaces:
            tokens.extend(adverb_surfaces)

        return [t for t in tokens if t]

    def _realize_subject(
        self,
        subject: Optional[SubjectSlot],
        morph: Any,
    ) -> str:
        if subject is None:
            return ""

        if isinstance(subject, str):
            return subject.strip()

        if isinstance(subject, Mapping):
            if hasattr(morph, "realize_np"):
                try:
                    return morph.realize_np(subject)
                except TypeError:
                    return morph.realize_np(
                        sem=dict(subject),
                        role="subject",
                        features=dict(subject.get("features", {})),
                    )
            return str(subject.get("surface") or subject.get("lemma") or "").strip()

        return str(subject).strip()

    def _realize_verb(
        self,
        features: Mapping[str, Any],
        morph: Any,
    ) -> str:
        verb_lemma = str(features.get("verb_lemma") or "").strip()
        if not verb_lemma:
            return ""

        verb_features: Dict[str, Any] = {
            "tense": features.get("tense", "present"),
            "aspect": features.get("aspect", "simple"),
            "polarity": features.get("polarity", "positive"),
            "voice": features.get("voice", "active"),
            "verb_role": "intransitive_event",
        }

        if hasattr(morph, "realize_verb"):
            try:
                return morph.realize_verb(verb_lemma, verb_features)
            except TypeError:
                return morph.realize_verb(lemma=verb_lemma, features=verb_features)

        return verb_lemma

    def _realize_adverbials(
        self,
        value: Any,
        morph: Any,
    ) -> List[str]:
        if value is None:
            return []

        if isinstance(value, (str, Mapping)):
            items = [value]
        elif isinstance(value, (list, tuple)):
            items = list(value)
        else:
            items = [value]

        surfaces: List[str] = []
        for adv in items:
            surface = self._realize_one_adverbial(adv, morph)
            if surface:
                surfaces.append(surface)
        return surfaces

    def _realize_one_adverbial(
        self,
        adv: Any,
        morph: Any,
    ) -> str:
        if adv is None:
            return ""

        if isinstance(adv, str):
            return adv.strip()

        if isinstance(adv, Mapping):
            if hasattr(morph, "realize_adverbial"):
                try:
                    return morph.realize_adverbial(adv)
                except TypeError:
                    return morph.realize_adverbial(dict(adv))
            return str(adv.get("surface") or adv.get("lemma") or "").strip()

        return str(adv).strip()


def realize_intransitive_event(
    slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> str:
    return IntransitiveEventConstruction().realize(slots, lang_profile, morph_api)


__all__ = [
    "IntransitiveEventConstruction",
    "realize_intransitive_event",
]