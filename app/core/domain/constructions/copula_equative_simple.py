# app/core/domain/constructions/copula_equative_simple.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Protocol

from .base import ClauseInput, ClauseOutput, Construction


__all__ = [
    "CONSTRUCTION_ID",
    "CopulaEquativeSimpleConstruction",
    "realize",
]


CONSTRUCTION_ID = "copula_equative_simple"


class MorphologyAPI(Protocol):
    """
    Minimal morphology interface expected by this construction.

    This module remains family-agnostic: the morphology layer owns NP building,
    predicate realization, and copula inflection.
    """

    def realize_subject(
        self,
        subject_data: Mapping[str, Any],
        lang_profile: Mapping[str, Any],
    ) -> str:
        ...

    def realize_predicate(
        self,
        predicate_data: Mapping[str, Any],
        lang_profile: Mapping[str, Any],
    ) -> str:
        ...

    def realize_copula(
        self,
        tense: str,
        subject_data: Mapping[str, Any],
        lang_profile: Mapping[str, Any],
    ) -> str:
        ...

    # Optional helpers
    def join_tokens(self, tokens: list[str]) -> str:
        ...

    def normalize_whitespace(self, text: str) -> str:
        ...


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {}
    if isinstance(value, str):
        cleaned = value.strip()
        return {"surface": cleaned} if cleaned else {}
    return {"value": value}


def _subject_from_roles(roles: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Normalize the subject slot into a morphology-friendly dict.

    Supported semantic / legacy inputs:
    - subject
    - subject_name (+ subject_features)
    """
    subject = roles.get("subject")
    if isinstance(subject, Mapping):
        return dict(subject)
    if isinstance(subject, str) and subject.strip():
        return {"name": subject.strip()}

    subject_name = _clean_text(roles.get("subject_name"))
    subject_features = _normalize_mapping(roles.get("subject_features"))

    if subject_name:
        payload: Dict[str, Any] = {"name": subject_name}
        if subject_features:
            payload["features"] = subject_features
        return payload

    return {}


def _predicate_from_roles(roles: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Normalize semantic slots into one predicate payload.

    Preferred semantic inputs:
    - predicate
    - predicate_nominal
    - profession
    - nationality

    Legacy / convenience inputs still accepted:
    - predicate_surface
    - profession_lemma
    - nationality_lemma
    """
    predicate = roles.get("predicate")
    if isinstance(predicate, Mapping):
        normalized = dict(predicate)
    elif isinstance(predicate, str) and predicate.strip():
        normalized = {"surface": predicate.strip()}
    else:
        normalized = {}

    predicate_nominal = roles.get("predicate_nominal")
    if isinstance(predicate_nominal, Mapping):
        normalized.setdefault("predicate_nominal", dict(predicate_nominal))
    elif isinstance(predicate_nominal, str) and predicate_nominal.strip():
        normalized.setdefault("predicate_nominal", {"surface": predicate_nominal.strip()})

    profession = roles.get("profession")
    if isinstance(profession, Mapping):
        normalized.setdefault("profession", dict(profession))
    elif isinstance(profession, str) and profession.strip():
        normalized.setdefault("profession", {"lemma": profession.strip()})

    nationality = roles.get("nationality")
    if isinstance(nationality, Mapping):
        normalized.setdefault("nationality", dict(nationality))
    elif isinstance(nationality, str) and nationality.strip():
        normalized.setdefault("nationality", {"lemma": nationality.strip()})

    # Legacy convenience keys still folded into the semantic predicate payload.
    profession_lemma = _clean_text(roles.get("profession_lemma"))
    if profession_lemma and "profession" not in normalized:
        normalized["profession"] = {"lemma": profession_lemma}

    nationality_lemma = _clean_text(roles.get("nationality_lemma"))
    if nationality_lemma and "nationality" not in normalized:
        normalized["nationality"] = {"lemma": nationality_lemma}

    predicate_surface = _clean_text(roles.get("predicate_surface"))
    if predicate_surface and not normalized:
        normalized["surface"] = predicate_surface

    predicate_features = _normalize_mapping(roles.get("predicate_features"))
    if predicate_features:
        merged_features = dict(normalized.get("features", {}))
        merged_features.update(predicate_features)
        normalized["features"] = merged_features

    return normalized


def _get_tense(features: Mapping[str, Any]) -> str:
    tense = features.get("tense", "present")
    if not isinstance(tense, str):
        return "present"
    tense = tense.strip().lower()
    return tense or "present"


def _copula_is_zero(tense: str, lang_profile: Mapping[str, Any]) -> bool:
    """
    Decide whether the copula should be omitted in this tense.
    """
    cop_cfg = lang_profile.get("copula")
    cop_cfg = dict(cop_cfg) if isinstance(cop_cfg, Mapping) else {}

    # Newer explicit switch wins if present.
    zero_cfg = cop_cfg.get("zero_copula")
    if isinstance(zero_cfg, Mapping):
        enabled = bool(zero_cfg.get("enabled", False))
        present_only = bool(zero_cfg.get("present_only", False))
        if enabled:
            return tense == "present" if present_only else True

    # Legacy flags still supported.
    if tense == "present":
        return bool(cop_cfg.get("present_zero", False))
    if tense == "past":
        return bool(cop_cfg.get("past_zero", False))

    return False


def _get_order(lang_profile: Mapping[str, Any], *, copula_zero: bool) -> str:
    """
    Resolve the linearization order for this construction.

    Supported patterns:
    - S-COP-PRED
    - S-PRED
    - PRED-COP-S
    """
    cop_cfg = lang_profile.get("copula")
    cop_cfg = dict(cop_cfg) if isinstance(cop_cfg, Mapping) else {}

    order = cop_cfg.get("order") or lang_profile.get("equative_template") or "S-COP-PRED"
    order = str(order).upper().replace(" ", "")

    if copula_zero and order == "S-COP-PRED":
        return "S-PRED"

    if order in {"S-COP-PRED", "S-PRED", "PRED-COP-S"}:
        return order

    return "S-PRED" if copula_zero else "S-COP-PRED"


def _join_tokens(tokens: list[str], morph_api: Any) -> str:
    cleaned = [t.strip() for t in tokens if isinstance(t, str) and t.strip()]
    if not cleaned:
        return ""

    if hasattr(morph_api, "join_tokens"):
        text = morph_api.join_tokens(cleaned)
    else:
        text = " ".join(cleaned)

    if hasattr(morph_api, "normalize_whitespace"):
        text = morph_api.normalize_whitespace(text)
    else:
        text = " ".join(text.split())

    return text.strip()


def _coerce_clause_input(abstract_slots: Mapping[str, Any]) -> ClauseInput:
    """
    Convert the module's compatibility dict shape into ClauseInput.

    This keeps legacy callers working while moving the implementation toward
    the shared construction runtime vocabulary.
    """
    roles: Dict[str, Any] = {
        "subject": _subject_from_roles(abstract_slots),
        "predicate": _predicate_from_roles(abstract_slots),
    }

    # Preserve extra semantic slots if callers already send them directly.
    for key in ("predicate_nominal", "profession", "nationality"):
        if key in abstract_slots and key not in roles:
            roles[key] = abstract_slots[key]

    features: Dict[str, Any] = {}
    for key in ("tense", "polarity", "person", "number"):
        if key in abstract_slots:
            features[key] = abstract_slots[key]

    return ClauseInput(roles=roles, features=features)


@dataclass(slots=True)
class CopulaEquativeSimpleConstruction(Construction):
    """
    Language-agnostic construction for simple equative clauses:

        SUBJECT (COPULA) PREDICATE
    """

    id: str = CONSTRUCTION_ID

    def realize_clause(
        self,
        abstract: ClauseInput,
        lang_profile: Dict[str, Any],
        morph: MorphologyAPI,
    ) -> ClauseOutput:
        subject_data = _normalize_mapping(abstract.roles.get("subject"))
        predicate_data = _normalize_mapping(abstract.roles.get("predicate"))

        tense = _get_tense(abstract.features)
        copula_zero = _copula_is_zero(tense, lang_profile)

        subject_str = _clean_text(morph.realize_subject(subject_data, lang_profile))
        predicate_str = _clean_text(morph.realize_predicate(predicate_data, lang_profile))

        copula_str = ""
        if not copula_zero:
            copula_str = _clean_text(morph.realize_copula(tense, subject_data, lang_profile))

        order = _get_order(lang_profile, copula_zero=copula_zero)

        tokens: list[str] = []
        if order == "S-PRED":
            if subject_str:
                tokens.append(subject_str)
            if predicate_str:
                tokens.append(predicate_str)
        elif order == "PRED-COP-S":
            if predicate_str:
                tokens.append(predicate_str)
            if copula_str:
                tokens.append(copula_str)
            if subject_str:
                tokens.append(subject_str)
        else:
            if subject_str:
                tokens.append(subject_str)
            if copula_str:
                tokens.append(copula_str)
            if predicate_str:
                tokens.append(predicate_str)

        text = _join_tokens(tokens, morph)

        return ClauseOutput(
            tokens=[t for t in tokens if t],
            text=text,
            metadata={
                "construction_id": self.id,
                "subject": subject_str,
                "copula": copula_str,
                "predicate": predicate_str,
                "slot_keys": sorted(k for k, v in abstract.roles.items() if v),
                "tense": tense,
                "copula_zero": copula_zero,
                "order": order,
            },
        )

    # Compatibility layer for older direct-dict callers.
    def realize(
        self,
        abstract_slots: Mapping[str, Any],
        lang_profile: Mapping[str, Any],
        morph_api: MorphologyAPI,
    ) -> Dict[str, Any]:
        abstract = _coerce_clause_input(abstract_slots)
        result = self.realize_clause(abstract, dict(lang_profile or {}), morph_api)
        return {
            "tokens": result.tokens,
            "text": result.text,
            "subject": result.metadata.get("subject", ""),
            "copula": result.metadata.get("copula", ""),
            "predicate": result.metadata.get("predicate", ""),
            "metadata": result.metadata,
        }


_CONSTRUCTION = CopulaEquativeSimpleConstruction()


def realize(
    abstract_slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> Dict[str, Any]:
    """
    Backward-compatible module entry point.

    Accepts the legacy dict-shaped payload but normalizes into shared semantic
    roles before realization.
    """
    return _CONSTRUCTION.realize(
        abstract_slots=abstract_slots or {},
        lang_profile=lang_profile or {},
        morph_api=morph_api,
    )