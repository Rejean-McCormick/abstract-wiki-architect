# app\core\domain\constructions\possession_have.py
"""
POSSESSION_HAVE CONSTRUCTION
----------------------------

Language-family-agnostic construction for possessive clauses of the form:

    "X has Y."

Examples:
    - "Marie Curie has two daughters."
    - "The city has many museums."

This construction is responsible for:

    - Choosing the linear order of POSSESSOR, VERB("have"), POSSESSED.
    - Passing the right role/feature information to the morphology layer.
    - Optionally allowing focus/fronting of the possessed NP (via pattern).

It is *not* responsible for:

    - Inflecting the verb ("have") for tense, person, number, polarity.
    - Internal morphology of NPs (plural, classifiers, gender, etc.).
    - Encoding alternative possession strategies ("to X there is Y" style).
      Those should use a different construction (e.g. POSSESSION_EXISTENTIAL).

Those tasks are delegated to the morphology / language-specific layer
via the `morph_api` object.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Protocol


CONSTRUCTION_ID = "possession_have"


__all__ = [
    "CONSTRUCTION_ID",
    "MorphologyAPI",
    "PossessionHaveConstruction",
    "render",
    "realize",
    "realize_possession_have",
]


class MorphologyAPI(Protocol):
    def realize_np(self, sem: Mapping[str, Any], role: str, features: Mapping[str, Any]) -> str:
        ...
    def realize_verb(self, lemma: str, features: Mapping[str, Any]) -> str:
        ...
    def join_tokens(self, tokens: list[str]) -> str:
        ...


def _normalize_spaces(text: str) -> str:
    return " ".join(str(text or "").split())


def _mapping_or_empty(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _get_possession_cfg(lang_profile: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Return the possession-have configuration.

    Primary shape:
        lang_profile["possession_have"] = {...}

    Compatibility fallback:
        top-level keys such as "pattern" / "verb_lemma".
    """
    profile = dict(lang_profile or {})
    cfg = profile.get("possession_have")
    if isinstance(cfg, Mapping):
        return dict(cfg)

    legacy = {}
    if "pattern" in profile:
        legacy["pattern"] = profile["pattern"]
    if "verb_lemma" in profile:
        legacy["verb_lemma"] = profile["verb_lemma"]
    if "possessor_role" in profile:
        legacy["possessor_role"] = profile["possessor_role"]
    if "possessed_role" in profile:
        legacy["possessed_role"] = profile["possessed_role"]
    return legacy


def _call_realize_np(
    morph_api: Any,
    *,
    sem: Mapping[str, Any],
    role: str,
    features: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
) -> str:
    """
    Best-effort dispatch for morphology implementations.

    Supported call shapes include:
    - realize_np(sem=..., role=..., features=...)
    - realize_np(sem=..., role=..., features=..., lang_profile=...)
    - realize_np(sem, role=..., lang_profile=...)
    """
    realize_np = getattr(morph_api, "realize_np", None)
    if not callable(realize_np):
        return _clean_text(sem.get("surface") or sem.get("lemma"))

    try:
        return str(
            realize_np(
                sem=sem,
                role=role,
                features=features,
                lang_profile=lang_profile,
            )
        )
    except TypeError:
        try:
            return str(realize_np(sem=sem, role=role, features=features))
        except TypeError:
            try:
                return str(realize_np(sem, role=role, lang_profile=lang_profile))
            except TypeError:
                return str(realize_np(sem, role=role))


def _call_realize_verb(
    morph_api: Any,
    *,
    lemma: str,
    features: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
) -> str:
    """
    Best-effort dispatch for verb realization.

    Supported call shapes include:
    - realize_verb(lemma=..., features=...)
    - realize_verb(lemma=..., features=..., lang_profile=...)
    """
    realize_verb = getattr(morph_api, "realize_verb", None)
    if not callable(realize_verb):
        return lemma

    try:
        return str(
            realize_verb(
                lemma=lemma,
                features=features,
                lang_profile=lang_profile,
            )
        )
    except TypeError:
        try:
            return str(realize_verb(lemma=lemma, features=features))
        except TypeError:
            try:
                return str(realize_verb(lemma, features, lang_profile=lang_profile))
            except TypeError:
                return str(realize_verb(lemma, features))


def _join_tokens(morph_api: Any, tokens: list[str]) -> str:
    cleaned = [_clean_text(t) for t in tokens if _clean_text(t)]
    if not cleaned:
        return ""

    join_tokens = getattr(morph_api, "join_tokens", None)
    if callable(join_tokens):
        return str(join_tokens(cleaned))

    return _normalize_spaces(" ".join(cleaned))


class PossessionHaveConstruction:
    """
    Batch-ready construction wrapper around the existing possession-have logic.
    """

    construction_id = CONSTRUCTION_ID
    required_slots = ("possessor", "possessed")

    def render(
        self,
        slots: Mapping[str, Any],
        lang_profile: Optional[Mapping[str, Any]],
        morph_api: Any,
    ) -> str:
        slot_map = dict(slots or {})
        profile = dict(lang_profile or {})

        possessor_sem = _mapping_or_empty(slot_map.get("possessor"))
        possessed_sem = _mapping_or_empty(slot_map.get("possessed"))

        # Preserve legacy forgiving behavior: return empty string rather than raise.
        if not possessor_sem or not possessed_sem:
            return ""

        tense = _clean_text(slot_map.get("tense") or "pres")
        polarity = _clean_text(slot_map.get("polarity") or "pos")
        aspect = _clean_text(slot_map.get("aspect") or "")

        possessive_cfg = _get_possession_cfg(profile)
        pattern = _clean_text(possessive_cfg.get("pattern") or "subj_verb_obj")
        verb_lemma = _clean_text(possessive_cfg.get("verb_lemma") or "have")
        possessor_role = _clean_text(possessive_cfg.get("possessor_role") or "possessor")
        possessed_role = _clean_text(possessive_cfg.get("possessed_role") or "possessed")

        possessor_features = _mapping_or_empty(possessor_sem.get("features"))
        possessed_features = _mapping_or_empty(possessed_sem.get("features"))

        possessor_np = _call_realize_np(
            morph_api,
            sem=possessor_sem,
            role=possessor_role,
            features=possessor_features,
            lang_profile=profile,
        )

        possessed_np = _call_realize_np(
            morph_api,
            sem=possessed_sem,
            role=possessed_role,
            features=possessed_features,
            lang_profile=profile,
        )

        verb_features: Dict[str, Any] = {
            "tense": tense,
            "polarity": polarity,
            "verb_role": "possession_have",
            "subject_features": possessor_features,
        }
        if aspect:
            verb_features["aspect"] = aspect

        # Allow callers/profile to pass through extra verb feature hints.
        if isinstance(slot_map.get("verb_features"), Mapping):
            verb_features.update(dict(slot_map["verb_features"]))
        if isinstance(possessive_cfg.get("verb_features"), Mapping):
            verb_features.update(dict(possessive_cfg["verb_features"]))

        verb = _call_realize_verb(
            morph_api,
            lemma=verb_lemma,
            features=verb_features,
            lang_profile=profile,
        )

        if pattern == "subj_obj_verb":
            tokens = [possessor_np, possessed_np, verb]
        elif pattern == "verb_subj_obj":
            tokens = [verb, possessor_np, possessed_np]
        elif pattern == "obj_verb_subj":
            tokens = [possessed_np, verb, possessor_np]
        elif pattern == "obj_subj_verb":
            tokens = [possessed_np, possessor_np, verb]
        else:
            # Default: subj_verb_obj
            tokens = [possessor_np, verb, possessed_np]

        return _join_tokens(morph_api, tokens)

    def realize(
        self,
        slots: Mapping[str, Any],
        lang_profile: Optional[Mapping[str, Any]],
        morph_api: Any,
    ) -> str:
        return self.render(slots, lang_profile, morph_api)


def render(
    slots: Mapping[str, Any],
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: Any,
) -> str:
    return PossessionHaveConstruction().render(slots, lang_profile, morph_api)


def realize(
    slots: Mapping[str, Any],
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: Any,
) -> str:
    """
    Backward-compatible functional entrypoint preserved for existing callers.
    """
    return render(slots, lang_profile, morph_api)


def realize_possession_have(
    slots: Mapping[str, Any],
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: Any,
) -> str:
    """
    Explicit convenience alias for code that prefers named realization helpers.
    """
    return render(slots, lang_profile, morph_api)