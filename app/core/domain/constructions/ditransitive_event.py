# app/core/domain/constructions/ditransitive_event.py

"""
DITRANSITIVE EVENT CONSTRUCTION
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
                     | "prepositional_for"
                     | "prepositional"
                     | "double_object"
                     | "dative_case",
        "recipient_adposition": "to",         # for prepositional strategies
        "recipient_position": "before_theme"  # or "after_theme" (for double object)
      }
    }

Morphology API (`morph_api`) is expected to implement:

    realize_np(np_spec: dict, role: str, lang_profile: dict) -> str
    realize_verb(verb_spec: dict, lang_profile: dict) -> str

This construction returns a list of surface tokens (strings) which can
then be joined by spaces by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Protocol


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


def _require_mapping(value: Any, *, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping/object.")
    return dict(value)


def _require_role_mapping(sem: Mapping[str, Any], role_name: str) -> Dict[str, Any]:
    value = sem.get(role_name)
    if not isinstance(value, Mapping):
        raise ValueError(f"Missing required role: {role_name}")
    normalized = dict(value)
    lemma = normalized.get("lemma") or normalized.get("surface")
    if not isinstance(lemma, str) or not lemma.strip():
        raise ValueError(
            f"Role '{role_name}' must provide a non-empty 'lemma' or 'surface'."
        )
    return normalized


def _merge_verb_features(
    verb_spec: Dict[str, Any], sem: Mapping[str, Any]
) -> Dict[str, Any]:
    """
    Merge tense/aspect/mood/negation from `sem` into the verb spec.
    """
    spec = dict(verb_spec) if verb_spec is not None else {}
    features = dict(spec.get("features", {}) or {})

    for key in ("tense", "aspect", "mood", "negated"):
        if key in sem:
            features[key] = sem[key]

    spec["features"] = features
    return spec


def _prepare_np_spec(
    np_sem: Optional[Mapping[str, Any]], case: Optional[str] = None
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


def _normalize_strategy(raw_strategy: Any) -> str:
    strategy = str(raw_strategy or "prepositional_to").strip().lower()

    alias_map = {
        "prepositional": "prepositional_to",
        "prepositional_recipient": "prepositional_to",
        "to_recipient": "prepositional_to",
        "for_recipient": "prepositional_for",
    }
    strategy = alias_map.get(strategy, strategy)

    if strategy not in {
        "prepositional_to",
        "prepositional_for",
        "double_object",
        "dative_case",
    }:
        return "prepositional_to"

    return strategy


def _resolve_recipient_adposition(strategy: str, ditr_cfg: Mapping[str, Any]) -> str:
    explicit = ditr_cfg.get("recipient_adposition")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    if strategy == "prepositional_for":
        return "for"

    return "to"


def _clean_surface(text: Any) -> Optional[str]:
    if text is None:
        return None
    value = str(text).strip()
    return value or None


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
    We treat the theme+recipient pair as an object cluster and keep their
    internal order as passed in.
    """
    objs: List[str] = []
    if theme:
        objs.append(theme)
    if recipient:
        objs.append(recipient)

    order = str(basic_word_order or "SVO").upper()

    if order == "SVO":
        parts = [subject, verb, *objs]
    elif order == "SOV":
        parts = [subject, *objs, verb]
    elif order == "VSO":
        parts = [verb, subject, *objs]
    elif order == "VOS":
        parts = [verb, *objs, subject]
    elif order == "OVS":
        parts = [*objs, verb, subject]
    elif order == "OSV":
        parts = [*objs, subject, verb]
    else:
        parts = [subject, verb, *objs]

    return [part for part in parts if _clean_surface(part)]


@dataclass
class DitransitiveEventConstruction:
    """
    Realizer for ditransitive events: AGENT V THEME (to/for) RECIPIENT.
    """

    id: str = "ditransitive_event"

    def realize(
        self,
        sem: Mapping[str, Any],
        lang_profile: Mapping[str, Any],
        morph_api: MorphAPI,
    ) -> List[str]:
        """
        Realize a ditransitive event as a list of surface tokens.

        Raises:
            ValueError: when required roles are missing or malformed.
        """
        sem_map = _require_mapping(sem, field_name="sem")
        profile = _require_mapping(lang_profile, field_name="lang_profile")

        verb_sem = _require_role_mapping(sem_map, "verb")
        agent_sem = _require_role_mapping(sem_map, "agent")
        theme_sem = _require_role_mapping(sem_map, "theme")
        recip_sem = _require_role_mapping(sem_map, "recipient")

        verb_spec = _merge_verb_features(verb_sem, sem_map)

        ditr_cfg = profile.get("ditransitive", {}) or {}
        if not isinstance(ditr_cfg, Mapping):
            ditr_cfg = {}

        strategy = _normalize_strategy(ditr_cfg.get("strategy"))
        recipient_position = str(
            ditr_cfg.get("recipient_position", "after_theme")
        ).strip().lower()
        recipient_adp = _resolve_recipient_adposition(strategy, ditr_cfg)

        if strategy == "dative_case":
            theme_spec = _prepare_np_spec(theme_sem, case=None)
            recip_spec = _prepare_np_spec(recip_sem, case="DAT")
        else:
            theme_spec = _prepare_np_spec(theme_sem, case=None)
            recip_spec = _prepare_np_spec(recip_sem, case=None)

        subject_form = _clean_surface(
            morph_api.realize_np(agent_sem, role="agent", lang_profile=dict(profile))
        )
        verb_form = _clean_surface(
            morph_api.realize_verb(verb_spec, lang_profile=dict(profile))
        )

        if not subject_form:
            raise ValueError("Failed to realize required role: agent")
        if not verb_form:
            raise ValueError("Failed to realize required role: verb")

        theme_form: Optional[str] = None
        if theme_spec:
            theme_form = _clean_surface(
                morph_api.realize_np(
                    theme_spec,
                    role="theme",
                    lang_profile=dict(profile),
                )
            )
        if not theme_form:
            raise ValueError("Failed to realize required role: theme")

        recip_form: Optional[str] = None
        if recip_spec:
            recip_np_form = _clean_surface(
                morph_api.realize_np(
                    recip_spec,
                    role="recipient",
                    lang_profile=dict(profile),
                )
            )
            if not recip_np_form:
                raise ValueError("Failed to realize required role: recipient")

            if strategy in {"prepositional_to", "prepositional_for"}:
                recip_form = _clean_surface(f"{recipient_adp} {recip_np_form}")
            else:
                recip_form = recip_np_form

        if strategy == "double_object" and recipient_position == "before_theme":
            primary_obj, secondary_obj = recip_form, theme_form
        else:
            primary_obj, secondary_obj = theme_form, recip_form

        basic_word_order = str(profile.get("basic_word_order", "SVO"))
        return _linearize(
            subject_form,
            verb_form,
            primary_obj,
            secondary_obj,
            basic_word_order=basic_word_order,
        )


def realize_ditransitive_event(
    sem: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
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