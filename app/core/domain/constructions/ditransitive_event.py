# constructions\ditransitive_event.py
# constructions/ditransitive_event.py

"""
DITRANSITIVE_EVENT CONSTRUCTION
-------------------------------

Language-independent clause template for ditransitive events of the form:

    AGENT V THEME to/for RECIPIENT

Examples (surface):
    "Marie Curie gave the prize to Pierre Curie."
    "She sent a letter to her sister."

This module does NOT perform any language-specific morphology. Instead it:

  * Chooses a linearization scheme based on the language profile
    (e.g. SVO, SOV, VSO, etc.).
  * Chooses how the recipient is marked:
      - double object (She gave him the book)
      - prepositional ("to" / "à" / "a")
      - dative case
  * Builds high-level NP and verb specs and delegates to `morph_api`.

Expected inputs
---------------

Semantics (`sem` dict) with keys:

    {
      "verb": {
        "lemma": "give",
        "features": { ... }    # optional, may be empty
      },
      "agent": {
        "lemma": "Marie Curie",
        "features": { ... }    # person, number, etc.
      },
      "theme": {
        "lemma": "the Nobel Prize",
        "features": { ... }
      },
      "recipient": {
        "lemma": "Pierre Curie",
        "features": { ... }
      },
      "tense": "past" | "present" | ...,
      "aspect": "perfective" | "imperfective" | ...,
      "mood": "indicative" | "subjunctive" | ...,
      "negated": bool
    }

Language profile (`lang_profile` dict) with typical keys:

    {
      "basic_word_order": "SVO" | "SOV" | "VSO" | "VOS" | "OVS" | "OSV",
      "ditransitive": {
        "strategy": "prepositional_to"
                     | "double_object"
                     | "dative_case",
        "recipient_adposition": "to",         # for 'prepositional_to'
        "recipient_position": "before_theme"  # or "after_theme" (for double_object)
      }
    }

Morphology API (`morph_api` object) is expected to implement:

    realize_np(np_spec: dict, role: str, lang_profile: dict) -> str
    realize_verb(verb_spec: dict, lang_profile: dict) -> str

This construction returns a list of surface tokens (strings) which can
then be joined by spaces by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


class MorphAPI(Protocol):
    """
    Minimal protocol expected from the morphology layer.
    """

    def realize_np(
        self, np_spec: Dict[str, Any], role: str, lang_profile: Dict[str, Any]
    ) -> str: ...

    def realize_verb(
        self, verb_spec: Dict[str, Any], lang_profile: Dict[str, Any]
    ) -> str: ...


def _merge_verb_features(
    verb_spec: Dict[str, Any], sem: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge tense/aspect/mood/negation from `sem` into the verb spec.
    """
    spec = dict(verb_spec) if verb_spec is not None else {}
    features = dict(spec.get("features", {}) or {})

    # Copy TAM / polarity from semantic layer if present.
    for key in ("tense", "aspect", "mood", "negated"):
        if key in sem:
            features[key] = sem[key]

    spec["features"] = features
    return spec


def _prepare_np_spec(
    np_sem: Optional[Dict[str, Any]], case: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Prepare an NP spec for the morphology API, optionally adding a case feature.
    """
    if not np_sem:
        return None

    spec = dict(np_sem)
    features = dict(spec.get("features", {}) or {})

    if case is not None:
        features["case"] = case

    spec["features"] = features
    return spec


def _linearize(
    subject: str,
    verb: str,
    theme: Optional[str],
    recipient: Optional[str],
    basic_word_order: str,
) -> List[str]:
    """
    Linearize subject, verb, theme, and recipient according to `basic_word_order`.

    `basic_word_order` is one of: SVO, SOV, VSO, VOS, OVS, OSV.
    We treat the theme+recipient pair as an "object cluster" and keep their
    internal order as passed in (theme first, then recipient).
    """
    # Object cluster (theme, recipient); allow either to be None.
    objs: List[str] = []
    if theme:
        objs.append(theme)
    if recipient:
        objs.append(recipient)

    order = basic_word_order.upper()

    if order == "SVO":
        return [x for x in (subject, verb, *objs) if x]
    if order == "SOV":
        return [x for x in (subject, *objs, verb) if x]
    if order == "VSO":
        return [x for x in (verb, subject, *objs) if x]
    if order == "VOS":
        return [x for x in (verb, *objs, subject) if x]
    if order == "OVS":
        return [x for x in (*objs, verb, subject) if x]
    if order == "OSV":
        return [x for x in (*objs, subject, verb) if x]

    # Fallback to SVO if we get something unexpected.
    return [x for x in (subject, verb, *objs) if x]


@dataclass
class DitransitiveEventConstruction:
    """
    Realizer for ditransitive events: AGENT V THEME (to/for) RECIPIENT.
    """

    id: str = "DITRANSITIVE_EVENT"

    def realize(
        self,
        sem: Dict[str, Any],
        lang_profile: Dict[str, Any],
        morph_api: MorphAPI,
    ) -> List[str]:
        """
        Realize a ditransitive event as a list of surface tokens.

        Args:
            sem:
                Semantic structure (see module docstring).
            lang_profile:
                Language profile with word-order + ditransitive strategy.
            morph_api:
                Object implementing MorphAPI.
        """
        # 1. Extract semantic pieces.
        verb_sem = sem.get("verb", {}) or {}
        agent_sem = sem.get("agent", {}) or {}
        theme_sem = sem.get("theme", {}) or {}
        recip_sem = sem.get("recipient", {}) or {}

        # 2. Prepare verb spec with TAM / polarity.
        verb_spec = _merge_verb_features(verb_sem, sem)

        # 3. Determine ditransitive strategy.
        ditr_cfg = lang_profile.get("ditransitive", {}) or {}
        strategy = ditr_cfg.get("strategy", "prepositional_to")
        recipient_position = ditr_cfg.get("recipient_position", "after_theme")
        recipient_adp = ditr_cfg.get("recipient_adposition", "to")

        # 4. Prepare NP specs (with case where needed).
        theme_spec: Optional[Dict[str, Any]] = theme_sem
        recip_spec: Optional[Dict[str, Any]] = recip_sem

        theme_form: Optional[str] = None
        recip_form: Optional[str] = None

        if strategy == "dative_case":
            # Recipient gets a dative case feature; theme is usually accusative or bare.
            theme_spec = _prepare_np_spec(theme_sem, case=None)
            recip_spec = _prepare_np_spec(recip_sem, case="DAT")
        else:
            # No special case marking; use whatever features are present.
            theme_spec = _prepare_np_spec(theme_sem, case=None)
            recip_spec = _prepare_np_spec(recip_sem, case=None)

        # 5. Realize subject NP and verb.
        subject_form = morph_api.realize_np(
            agent_sem, role="agent", lang_profile=lang_profile
        )
        verb_form = morph_api.realize_verb(verb_spec, lang_profile=lang_profile)

        # 6. Realize theme NP.
        if theme_spec:
            theme_form = morph_api.realize_np(
                theme_spec, role="theme", lang_profile=lang_profile
            )

        # 7. Realize recipient NP according to strategy.
        if recip_spec:
            recip_np_form = morph_api.realize_np(
                recip_spec, role="recipient", lang_profile=lang_profile
            )
            if strategy == "prepositional_to":
                # Add adposition before recipient NP.
                recip_form = f"{recipient_adp} {recip_np_form}"
            else:
                # double_object or dative_case: bare NP (case already encoded in spec if needed).
                recip_form = recip_np_form

        # 8. For double_object strategy, we may want recipient before theme.
        if strategy == "double_object" and recipient_position == "before_theme":
            # Switch the order: recipient, then theme.
            primary_obj, secondary_obj = recip_form, theme_form
        else:
            # Default: theme, then recipient.
            primary_obj, secondary_obj = theme_form, recip_form

        basic_word_order = lang_profile.get("basic_word_order", "SVO")
        tokens = _linearize(
            subject_form,
            verb_form,
            primary_obj,
            secondary_obj,
            basic_word_order=basic_word_order,
        )

        # Strip out any accidental empty segments.
        return [t for t in tokens if t]


def realize_ditransitive_event(
    sem: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: MorphAPI,
) -> List[str]:
    """
    Convenience function: functional interface around DitransitiveEventConstruction.
    """
    return DitransitiveEventConstruction().realize(sem, lang_profile, morph_api)


__all__ = [
    "DitransitiveEventConstruction",
    "realize_ditransitive_event",
    "MorphAPI",
]