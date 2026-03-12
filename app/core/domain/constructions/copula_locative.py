# app/core/domain/constructions/copula_locative.py
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .base import ClauseInput, ClauseOutput, Construction
from .slot_models import SlotSignature, SlotSpec, SlotValueKind

COPULA_LOCATIVE_ID = "copula_locative"
LEGACY_CONSTRUCTION_ID = "COPULA_LOCATIVE"
DEFAULT_TEMPLATE: tuple[str, ...] = ("SUBJ", "COP", "LOC_PHRASE")

COPULA_LOCATIVE_SIGNATURE = SlotSignature(
    required=(
        SlotSpec(
            name="subject",
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Subject NP or surface string.",
        ),
    ),
    optional=(
        SlotSpec(
            name="location",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Location NP / entity / surface string.",
        ),
        SlotSpec(
            name="adposition_type",
            required=False,
            accepted_kinds=(SlotValueKind.LITERAL,),
            allow_raw_string_fallback=True,
            description="Logical locative relation such as in/at/on.",
            default_value="in",
        ),
        SlotSpec(
            name="copula_features",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Optional copula feature bundle.",
        ),
    ),
    allow_additional_slots=True,
)


def _normalize_spaces(text: str) -> str:
    return " ".join((text or "").split())


def _copy_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _surface_from_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        for key in ("surface", "surface_hint", "label", "name", "lemma"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    for key in ("surface", "surface_hint", "label", "name", "lemma"):
        raw = getattr(value, key, None)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return str(value).strip()


def _slot_features(value: Any) -> dict[str, Any]:
    features: dict[str, Any] = {}

    if isinstance(value, Mapping):
        nested = value.get("features")
        if isinstance(nested, Mapping):
            features.update(dict(nested))

        for key in ("gender", "number", "person", "case", "definiteness", "proper"):
            if key in value and value[key] is not None:
                features[key] = value[key]
        return features

    nested = getattr(value, "features", None)
    if isinstance(nested, Mapping):
        features.update(dict(nested))

    for key in ("gender", "number", "person", "case", "definiteness", "proper"):
        raw = getattr(value, key, None)
        if raw is not None:
            features[key] = raw

    return features


def _template(lang_profile: Mapping[str, Any] | None) -> tuple[str, ...]:
    profile = dict(lang_profile or {})
    raw = profile.get("locative_template", DEFAULT_TEMPLATE)

    if isinstance(raw, str):
        items = tuple(part.strip() for part in raw.split() if part.strip())
        return items or DEFAULT_TEMPLATE

    if isinstance(raw, Sequence):
        items = tuple(str(part).strip() for part in raw if str(part).strip())
        return items or DEFAULT_TEMPLATE

    return DEFAULT_TEMPLATE


def _join_tokens(tokens: list[str], morph_api: Any) -> str:
    cleaned = [t.strip() for t in tokens if isinstance(t, str) and t.strip()]
    if not cleaned:
        return ""

    if hasattr(morph_api, "join_tokens"):
        try:
            return _normalize_spaces(str(morph_api.join_tokens(cleaned) or ""))
        except TypeError:
            pass

    return _normalize_spaces(" ".join(cleaned))


def _call_realize_np(value: Any, role: str, morph_api: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if hasattr(morph_api, "realize_np"):
        features = _slot_features(value)
        try:
            return _normalize_spaces(
                str(
                    morph_api.realize_np(
                        sem=value,
                        role=role,
                        features=features,
                    )
                    or ""
                )
            )
        except TypeError:
            try:
                return _normalize_spaces(
                    str(morph_api.realize_np(value, role=role, features=features) or "")
                )
            except TypeError:
                try:
                    return _normalize_spaces(str(morph_api.realize_np(value) or ""))
                except TypeError:
                    pass

    return _surface_from_value(value)


def _call_realize_noun(
    lemma: str,
    *,
    features: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: Any,
) -> str:
    if not lemma:
        return ""

    if hasattr(morph_api, "realize_noun"):
        try:
            return _normalize_spaces(
                str(
                    morph_api.realize_noun(
                        lemma=lemma,
                        features=dict(features),
                        lang_profile=dict(lang_profile),
                    )
                    or ""
                )
            )
        except TypeError:
            try:
                return _normalize_spaces(
                    str(morph_api.realize_noun(lemma, dict(features), dict(lang_profile)) or "")
                )
            except TypeError:
                try:
                    return _normalize_spaces(str(morph_api.realize_noun(lemma, dict(features)) or ""))
                except TypeError:
                    pass

    return lemma.strip()


def _call_realize_copula(
    *,
    features: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: Any,
) -> str:
    if not hasattr(morph_api, "realize_copula"):
        return ""

    try:
        return _normalize_spaces(
            str(
                morph_api.realize_copula(
                    features=dict(features),
                    lang_profile=dict(lang_profile),
                )
                or ""
            )
        )
    except TypeError:
        try:
            return _normalize_spaces(
                str(morph_api.realize_copula(dict(features), dict(lang_profile)) or "")
            )
        except TypeError:
            try:
                return _normalize_spaces(str(morph_api.realize_copula(dict(features)) or ""))
            except TypeError:
                return ""


def _call_realize_adposition(
    adposition_type: str,
    *,
    lang_profile: Mapping[str, Any],
    morph_api: Any,
) -> str:
    if not adposition_type or not hasattr(morph_api, "realize_adposition"):
        return ""

    try:
        return _normalize_spaces(
            str(
                morph_api.realize_adposition(
                    adposition_type=adposition_type,
                    lang_profile=dict(lang_profile),
                )
                or ""
            )
        )
    except TypeError:
        try:
            return _normalize_spaces(
                str(morph_api.realize_adposition(adposition_type, dict(lang_profile)) or "")
            )
        except TypeError:
            try:
                return _normalize_spaces(str(morph_api.realize_adposition(adposition_type) or ""))
            except TypeError:
                return ""


def _should_drop_copula(
    copula_form: str,
    copula_features: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
) -> bool:
    if not copula_form:
        return True

    zero_cfg = dict(lang_profile.get("zero_copula", {}) or {})
    if not bool(zero_cfg.get("enabled", False)):
        return False

    tense = str(copula_features.get("tense", "present") or "present")
    present_only = bool(zero_cfg.get("present_only", True))
    if present_only and tense != "present":
        return False

    return True


def _normalize_location_spec(slots: Mapping[str, Any]) -> Any:
    if "location" in slots and slots.get("location") is not None:
        return slots.get("location")

    surface = slots.get("location_surface")
    if isinstance(surface, str) and surface.strip():
        return surface.strip()

    lemma = slots.get("location_lemma")
    if not isinstance(lemma, str) or not lemma.strip():
        return None

    spec = {
        "lemma": lemma.strip(),
        "features": _copy_mapping(slots.get("location_features")),
    }
    return spec


def _build_locative_phrase(
    location: Any,
    *,
    adposition_type: str,
    lang_profile: Mapping[str, Any],
    morph_api: Any,
) -> str:
    if location is None:
        return ""

    if isinstance(location, str):
        location_np = location.strip()
    elif isinstance(location, Mapping):
        if isinstance(location.get("surface"), str) and location["surface"].strip():
            location_np = location["surface"].strip()
        elif isinstance(location.get("surface_hint"), str) and location["surface_hint"].strip():
            location_np = location["surface_hint"].strip()
        elif any(k in location for k in ("label", "name")) and hasattr(morph_api, "realize_np"):
            location_np = _call_realize_np(location, "location", morph_api)
        else:
            lemma = str(location.get("lemma") or location.get("name") or location.get("label") or "").strip()
            location_np = _call_realize_noun(
                lemma,
                features=_slot_features(location),
                lang_profile=lang_profile,
                morph_api=morph_api,
            )
    else:
        location_np = _call_realize_np(location, "location", morph_api)

    location_np = _normalize_spaces(location_np)
    if not location_np:
        return ""

    if not bool(lang_profile.get("use_adpositions", True)):
        return location_np

    adposition = _call_realize_adposition(
        adposition_type,
        lang_profile=lang_profile,
        morph_api=morph_api,
    )
    if not adposition:
        return location_np

    order = str(lang_profile.get("locative_adposition_order", "preposition") or "preposition").lower()
    if order == "postposition":
        return _join_tokens([location_np, adposition], morph_api)

    return _join_tokens([adposition, location_np], morph_api)


def to_clause_input(slots: Mapping[str, Any]) -> ClauseInput:
    raw = dict(slots or {})
    copula_features = _copy_mapping(raw.get("copula_features"))

    for key in ("tense", "polarity", "person", "number"):
        if key in raw and key not in copula_features and raw[key] is not None:
            copula_features[key] = raw[key]

    roles = {
        "SUBJ": raw.get("subject"),
        "LOCATION": _normalize_location_spec(raw),
    }
    features = {
        "adposition_type": raw.get("adposition_type", "in"),
        "copula_features": copula_features,
    }
    return ClauseInput(roles=roles, features=features)


class CopulaLocativeConstruction(Construction):
    id = COPULA_LOCATIVE_ID
    legacy_id = LEGACY_CONSTRUCTION_ID
    slot_signature = COPULA_LOCATIVE_SIGNATURE

    def realize_clause(
        self,
        abstract: ClauseInput,
        lang_profile: Mapping[str, Any],
        morph: Any,
    ) -> ClauseOutput:
        lang_profile = dict(lang_profile or {})

        subject = _call_realize_np(abstract.roles.get("SUBJ"), "subject", morph)
        location = abstract.roles.get("LOCATION")
        adposition_type = str(abstract.features.get("adposition_type", "in") or "in")

        raw_copula_features = abstract.features.get("copula_features")
        copula_features = _copy_mapping(raw_copula_features)

        copula_surface = _call_realize_copula(
            features=copula_features,
            lang_profile=lang_profile,
            morph_api=morph,
        )
        if _should_drop_copula(copula_surface, copula_features, lang_profile):
            copula_surface = ""

        loc_phrase = _build_locative_phrase(
            location,
            adposition_type=adposition_type,
            lang_profile=lang_profile,
            morph_api=morph,
        )

        token_map = {
            "SUBJ": subject,
            "COP": copula_surface,
            "LOC_PHRASE": loc_phrase,
        }

        tokens: list[str] = []
        for symbol in _template(lang_profile):
            token = token_map.get(symbol, "")
            if token:
                tokens.append(token)

        text = _join_tokens(tokens, morph)

        return ClauseOutput(
            tokens=tokens,
            text=text,
            metadata={
                "construction_id": self.id,
                "legacy_construction_id": self.legacy_id,
                "template": list(_template(lang_profile)),
                "zero_copula": not bool(copula_surface),
                "adposition_type": adposition_type,
                "location_present": bool(loc_phrase),
            },
        )

    def realize(
        self,
        slots: Mapping[str, Any],
        lang_profile: Mapping[str, Any],
        morph_api: Any,
    ) -> dict[str, Any]:
        output = self.realize_clause(to_clause_input(slots), lang_profile, morph_api)
        return {
            "construction_id": self.id,
            "tokens": list(output.tokens),
            "text": output.text,
            "metadata": dict(output.metadata),
        }


_CONSTRUCTION = CopulaLocativeConstruction()


def realize(
    slots: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: Any,
) -> dict[str, Any]:
    return _CONSTRUCTION.realize(slots, lang_profile, morph_api)


def render(
    slots: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: Any,
) -> str:
    return _CONSTRUCTION.realize_clause(
        to_clause_input(slots),
        dict(lang_profile or {}),
        morph_api,
    ).text


__all__ = [
    "COPULA_LOCATIVE_ID",
    "COPULA_LOCATIVE_SIGNATURE",
    "CopulaLocativeConstruction",
    "to_clause_input",
    "realize",
    "render",
]