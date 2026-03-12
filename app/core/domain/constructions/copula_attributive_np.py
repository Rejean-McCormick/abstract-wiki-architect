# app/core/domain/constructions/copula_attributive_np.py

"""
COPULA ATTRIBUTIVE NOMINAL CONSTRUCTION
---------------------------------------

Family-agnostic realization for clauses of the form:

    X is (a) Y

Examples:
    "Marie Curie is a Pole."
    "Marie Curie is a Catholic."
    "The Nile is a river."

Migration notes
---------------
This module now exposes:

- a stable construction id,
- canonical semantic slot names,
- a typed slots object for new code,
- a backward-compatible `render(...)` wrapper for legacy callers.

Canonical semantic slots:
    - subject
    - predicate_nominal

Legacy compatibility keys still accepted by `render(...)`:
    - predicate_lemma
    - predicate_features
    - article_type
    - copula_features
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence

CONSTRUCTION_ID = "copula_attributive_np"

CANONICAL_SLOT_NAMES = (
    "subject",
    "predicate_nominal",
)

LEGACY_SLOT_ALIASES = {
    "predicate_lemma": "predicate_nominal.lemma",
    "predicate_features": "predicate_nominal.features",
    "article_type": "predicate_nominal.article_type",
    "copula_features": "copula",
}

__all__ = [
    "CONSTRUCTION_ID",
    "CANONICAL_SLOT_NAMES",
    "LEGACY_SLOT_ALIASES",
    "MorphologyAPI",
    "CopulaAttributiveNPSlots",
    "realize_copula_attributive_np",
    "render",
]


class MorphologyAPI(Protocol):
    """
    Minimal protocol for morphology backends used by this construction.
    """

    def realize_copula(
        self,
        features: Mapping[str, Any],
        lang_profile: Optional[Mapping[str, Any]] = None,
    ) -> str:
        ...

    def realize_noun(
        self,
        lemma: str,
        features: Mapping[str, Any],
        lang_profile: Optional[Mapping[str, Any]] = None,
    ) -> str:
        ...

    def realize_article(
        self,
        noun_form: str,
        features: Mapping[str, Any],
        article_type: str,
        lang_profile: Optional[Mapping[str, Any]] = None,
    ) -> str:
        ...

    # Optional compatibility hook used when subject is structured.
    def realize_np(
        self,
        role: str,
        lemma: str,
        features: Mapping[str, Any],
    ) -> str:
        ...


@dataclass
class CopulaAttributiveNPSlots:
    """
    Typed construction input for COPULA_ATTRIBUTIVE_NP.

    New planner/bridge code should prefer this shape. Legacy dict callers
    are still supported through `render(...)`.
    """

    subject: Any

    # Canonical predicate_nominal payload flattened for convenience
    predicate_lemma: str = ""
    predicate_surface: Optional[str] = None
    predicate_number: str = "sg"
    predicate_gender: Optional[str] = None
    article_type: str = "indefinite"

    # Clause / copula features
    tense: str = "present"
    polarity: str = "positive"
    person: int = 3
    subject_number: str = "sg"

    # Extensibility
    extra_subject_features: Dict[str, Any] = field(default_factory=dict)
    extra_predicate_features: Dict[str, Any] = field(default_factory=dict)
    extra_copula_features: Dict[str, Any] = field(default_factory=dict)


def _mapping_or_empty(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalize_spaces(text: str) -> str:
    return " ".join(str(text or "").split())


def _get_template(lang_profile: Mapping[str, Any]) -> str:
    """
    Accept either:
      - a new-style format string, or
      - the legacy token-order list from the previous implementation.
    """
    template = lang_profile.get("attributive_np_template")

    if isinstance(template, str) and template.strip():
        return template

    if isinstance(template, Sequence) and not isinstance(template, (str, bytes)):
        mapping = {
            "SUBJ": "{SUBJ}",
            "COP": "{COP}",
            "PRED_NP": "{PRED_NP}",
        }
        parts = [mapping[symbol] for symbol in template if symbol in mapping]
        if parts:
            return " ".join(parts)

    return "{SUBJ} {COP} {PRED_NP}"


def _should_drop_copula(
    copula_form: str,
    *,
    tense: str,
    lang_profile: Mapping[str, Any],
) -> bool:
    """
    Decide whether to omit the copula.

    Supported compatibility controls:
      - enforce_zero_copula: bool
      - zero_copula.enabled: bool
      - zero_copula.present_only: bool
    """
    if not copula_form:
        return True

    if bool(lang_profile.get("enforce_zero_copula", False)):
        return True

    zero_cfg = _mapping_or_empty(lang_profile.get("zero_copula"))
    if not zero_cfg.get("enabled", False):
        return False

    present_only = bool(zero_cfg.get("present_only", True))
    normalized_tense = (tense or "present").strip().lower()

    if present_only and normalized_tense not in {"present", "pres", ""}:
        return False

    return True


def _coerce_slots(slots: Mapping[str, Any] | CopulaAttributiveNPSlots) -> CopulaAttributiveNPSlots:
    """
    Accept both the new typed slots object and the legacy dict shape.

    Canonical slot support:
      slots["predicate_nominal"] = {
          "lemma": "...",
          "surface": "...",
          "features": {...},
          "article_type": "indefinite",
      }

    Legacy slot support:
      slots["predicate_lemma"]
      slots["predicate_features"]
      slots["article_type"]
      slots["copula_features"]
    """
    if isinstance(slots, CopulaAttributiveNPSlots):
        return slots

    data = dict(slots or {})
    predicate_nominal = data.get("predicate_nominal")
    legacy_predicate_features = _mapping_or_empty(data.get("predicate_features"))
    legacy_copula_features = _mapping_or_empty(data.get("copula_features"))

    predicate_lemma = str(data.get("predicate_lemma") or "").strip()
    predicate_surface = data.get("predicate_surface")
    article_type = str(data.get("article_type") or "indefinite")

    merged_predicate_features: Dict[str, Any] = {}

    if isinstance(predicate_nominal, Mapping):
        merged_predicate_features.update(_mapping_or_empty(predicate_nominal.get("features")))
        if not predicate_lemma:
            predicate_lemma = str(
                predicate_nominal.get("lemma")
                or predicate_nominal.get("name")
                or ""
            ).strip()
        if predicate_surface is None:
            predicate_surface = predicate_nominal.get("surface")
        if "article_type" not in data and predicate_nominal.get("article_type"):
            article_type = str(predicate_nominal["article_type"])

    merged_predicate_features.update(legacy_predicate_features)

    tense = str(data.get("tense") or legacy_copula_features.get("tense") or "present")
    polarity = str(data.get("polarity") or legacy_copula_features.get("polarity") or "positive")
    person = int(data.get("person") or legacy_copula_features.get("person") or 3)
    subject_number = str(
        data.get("subject_number")
        or legacy_copula_features.get("number")
        or data.get("number")
        or "sg"
    )

    return CopulaAttributiveNPSlots(
        subject=data.get("subject", ""),
        predicate_lemma=predicate_lemma,
        predicate_surface=str(predicate_surface).strip() if predicate_surface else None,
        predicate_number=str(merged_predicate_features.get("number") or "sg"),
        predicate_gender=merged_predicate_features.get("gender"),
        article_type=article_type,
        tense=tense,
        polarity=polarity,
        person=person,
        subject_number=subject_number,
        extra_subject_features=_mapping_or_empty(data.get("subject_features")),
        extra_predicate_features=merged_predicate_features,
        extra_copula_features=legacy_copula_features,
    )


def _realize_subject_np(
    subject: Any,
    morph_api: MorphologyAPI,
    *,
    extra_features: Mapping[str, Any],
) -> str:
    """
    Subject can be:
      - a ready surface string,
      - a structured mapping with name/lemma/features.
    """
    if isinstance(subject, str):
        return subject.strip()

    if isinstance(subject, Mapping):
        surface = str(subject.get("surface") or subject.get("name") or "").strip()
        lemma = subject.get("lemma") or subject.get("name") or subject.get("surface")

        if hasattr(morph_api, "realize_np") and lemma:
            features = {"role": "subject"}
            features.update(_mapping_or_empty(subject.get("features")))
            features.update(dict(extra_features))
            try:
                realized = morph_api.realize_np(
                    role="subject",
                    lemma=str(lemma),
                    features=features,
                )
                return _normalize_spaces(realized)
            except TypeError:
                # Conservative fallback for looser morphology adapters.
                return surface or str(lemma).strip()

        return surface

    return str(subject or "").strip()


def _build_predicate_np(
    slots: CopulaAttributiveNPSlots,
    lang_profile: Mapping[str, Any],
    morph_api: MorphologyAPI,
) -> str:
    """
    Build the predicate nominal phrase.

    New path:
      - canonical predicate_nominal semantics
    Legacy compatibility:
      - predicate_lemma + predicate_features + article_type
    """
    if slots.predicate_surface:
        return _normalize_spaces(slots.predicate_surface)

    if not slots.predicate_lemma:
        return ""

    predicate_features: Dict[str, Any] = {
        "role": "predicate_nominal",
        "number": slots.predicate_number,
    }
    if slots.predicate_gender is not None:
        predicate_features["gender"] = slots.predicate_gender
    predicate_features.update(slots.extra_predicate_features)

    noun_form = ""
    if hasattr(morph_api, "realize_noun"):
        noun_form = morph_api.realize_noun(
            lemma=slots.predicate_lemma,
            features=predicate_features,
            lang_profile=lang_profile,
        )
    elif hasattr(morph_api, "realize_np"):
        noun_form = morph_api.realize_np(
            role="predicate_nominal",
            lemma=slots.predicate_lemma,
            features=predicate_features,
        )
    else:
        noun_form = slots.predicate_lemma

    noun_form = _normalize_spaces(noun_form)
    if not noun_form:
        return ""

    if slots.article_type == "none" or not bool(lang_profile.get("use_articles", True)):
        return noun_form

    article_form = ""
    if hasattr(morph_api, "realize_article"):
        article_form = morph_api.realize_article(
            noun_form=noun_form,
            features=predicate_features,
            article_type=slots.article_type,
            lang_profile=lang_profile,
        ) or ""

    return _normalize_spaces(f"{article_form} {noun_form}")


def _realize_copula(
    slots: CopulaAttributiveNPSlots,
    lang_profile: Mapping[str, Any],
    morph_api: MorphologyAPI,
) -> str:
    copula_features: Dict[str, Any] = {
        "tense": slots.tense,
        "polarity": slots.polarity,
        "person": slots.person,
        "number": slots.subject_number,
    }
    copula_features.update(slots.extra_copula_features)

    try:
        copula = morph_api.realize_copula(
            copula_features,
            lang_profile=lang_profile,
        )
    except TypeError:
        copula = morph_api.realize_copula(copula_features)

    copula = _normalize_spaces(copula)

    if _should_drop_copula(copula, tense=slots.tense, lang_profile=lang_profile):
        return ""

    return copula


def realize_copula_attributive_np(
    slots: CopulaAttributiveNPSlots,
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: MorphologyAPI,
) -> str:
    """
    Realize a COPULA_ATTRIBUTIVE_NP clause using the typed slot contract.
    """
    lang_profile = dict(lang_profile or {})

    subject_np = _realize_subject_np(
        slots.subject,
        morph_api,
        extra_features=slots.extra_subject_features,
    )
    predicate_np = _build_predicate_np(slots, lang_profile, morph_api)
    copula = _realize_copula(slots, lang_profile, morph_api)

    template = _get_template(lang_profile)
    sentence = template.format(
        SUBJ=subject_np,
        COP=copula,
        PRED_NP=predicate_np,
    )
    return _normalize_spaces(sentence)


def render(
    slots: Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph_api: MorphologyAPI,
) -> str:
    """
    Backward-compatible legacy entrypoint.

    This preserves the old module API while normalizing legacy keys into the
    typed construction input.
    """
    normalized = _coerce_slots(slots)
    return realize_copula_attributive_np(
        normalized,
        lang_profile=lang_profile,
        morph_api=morph_api,
    )