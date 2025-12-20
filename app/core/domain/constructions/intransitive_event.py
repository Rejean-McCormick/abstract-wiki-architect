# app\core\domain\constructions\intransitive_event.py
# constructions\intransitive_event.py
"""
Intransitive event construction.

Language-agnostic clause pattern for intransitive predicates, e.g.:

    "The conference took place in Paris."
    "Marie Curie died in 1934."

This construction handles:
- Subject realization (NP or pre-surfaced string).
- Intransitive verb inflection (tense/aspect/polarity etc.).
- Simple placement of adverbials (time/place/manner), guided by the
  language profile.

It delegates morphology to `morph_api` and word-order preferences to
`lang_profile`.
"""

from typing import Any, Dict, List, Optional, Union

from .base import BaseConstruction  # expected to define the interface for constructions

SubjectSlot = Union[str, Dict[str, Any]]
AdverbialSlot = Union[str, Dict[str, Any]]


class IntransitiveEventConstruction(BaseConstruction):
    """
    Core intransitive-event construction.

    Expected slots:
        slots = {
            "subject": <SubjectSlot>,           # required
            "verb_lemma": str,                  # required
            "tense": str = "present",          # optional
            "aspect": str = "simple",          # optional
            "polarity": str = "positive",      # optional
            "voice": str = "active",           # optional, usually "active"
            "adverbials": List[AdverbialSlot]  # optional
        }

    `lang_profile`:
        - "basic_word_order": one of {"SVO", "SOV", "VSO", "VOS", "OSV", "OVS"}
        - "intransitive_adverb_position": one of
              {"after_verb", "before_verb", "sentence_final"}
          (defaults to "after_verb" if missing)

    `morph_api` is expected to provide:
        - realize_np(np_spec: Dict[str, Any]) -> str
        - realize_verb(lemma: str, features: Dict[str, Any]) -> str
        - realize_adverbial(adv_spec: Dict[str, Any]) -> str  (optional)
    """

    id: str = "INTRANSITIVE_EVENT"

    def realize(
        self,
        slots: Dict[str, Any],
        lang_profile: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        subject_surface = self._realize_subject(slots.get("subject"), morph_api)
        verb_surface = self._realize_verb(slots, subject_surface, morph_api)
        adverb_surfaces = self._realize_adverbials(
            slots.get("adverbials", []), morph_api
        )

        basic_word_order = lang_profile.get("basic_word_order", "SVO")
        adv_position = lang_profile.get("intransitive_adverb_position", "after_verb")

        tokens: List[str] = []

        if basic_word_order in ("SVO", "SOV", "OSV", "OVS"):
            # Default intransitive: S V for SVO/SOV-like systems
            if adv_position == "before_verb" and adverb_surfaces:
                tokens.extend([subject_surface] + adverb_surfaces + [verb_surface])
            else:
                tokens.append(subject_surface)
                tokens.append(verb_surface)
                if adv_position in ("after_verb", "sentence_final") and adverb_surfaces:
                    tokens.extend(adverb_surfaces)

        elif basic_word_order in ("VSO", "VOS"):
            # VS for intransitives in VSO/VOS systems
            if adv_position == "before_verb" and adverb_surfaces:
                tokens.extend(adverb_surfaces)
                tokens.extend([verb_surface, subject_surface])
            else:
                tokens.extend([verb_surface, subject_surface])
                if adv_position in ("after_verb", "sentence_final") and adverb_surfaces:
                    tokens.extend(adverb_surfaces)
        else:
            # Fallback: treat as SVO
            if adv_position == "before_verb" and adverb_surfaces:
                tokens.extend([subject_surface] + adverb_surfaces + [verb_surface])
            else:
                tokens.append(subject_surface)
                tokens.append(verb_surface)
                if adv_position in ("after_verb", "sentence_final") and adverb_surfaces:
                    tokens.extend(adverb_surfaces)

        # Simple whitespace join; punctuation handled upstream or downstream
        return " ".join(t for t in tokens if t)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _realize_subject(self, subject: Optional[SubjectSlot], morph_api: Any) -> str:
        if subject is None:
            # Extremely degenerate; caller should normally provide a subject
            return ""

        if isinstance(subject, str):
            return subject

        if isinstance(subject, dict):
            # Delegate NP realization to morph_api
            if hasattr(morph_api, "realize_np"):
                return morph_api.realize_np(subject)
            # Fallback: try simple "lemma" field
            lemma = subject.get("lemma") or subject.get("surface") or ""
            return str(lemma)

        # Last-resort fallback
        return str(subject)

    def _realize_verb(
        self,
        slots: Dict[str, Any],
        subject_surface: str,
        morph_api: Any,
    ) -> str:
        verb_lemma = slots.get("verb_lemma", "")
        if not verb_lemma:
            return ""

        features: Dict[str, Any] = {
            "tense": slots.get("tense", "present"),
            "aspect": slots.get("aspect", "simple"),
            "polarity": slots.get("polarity", "positive"),
            "voice": slots.get("voice", "active"),
            # Optionally, subject agreement features could be attached here
        }

        if hasattr(morph_api, "realize_verb"):
            return morph_api.realize_verb(verb_lemma, features)

        # Fallback: no inflection, return lemma
        return verb_lemma

    def _realize_adverbials(
        self,
        adverbials: List[AdverbialSlot],
        morph_api: Any,
    ) -> List[str]:
        surfaces: List[str] = []
        for adv in adverbials:
            if isinstance(adv, str):
                surfaces.append(adv)
            elif isinstance(adv, dict):
                if hasattr(morph_api, "realize_adverbial"):
                    surfaces.append(morph_api.realize_adverbial(adv))
                else:
                    lemma = adv.get("lemma") or adv.get("surface") or ""
                    surfaces.append(str(lemma))
            else:
                surfaces.append(str(adv))
        return [s for s in surfaces if s]
