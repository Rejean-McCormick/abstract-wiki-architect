# app/adapters/engines/engines/germanic.py
"""
GERMANIC LANGUAGE ENGINE
------------------------
Compatibility renderer for Germanic languages (EN, DE, NL, SV, DA, NO).

This module stays on the legacy family-engine surface:

    render_bio(name, gender, prof_lemma, nat_lemma, config) -> str

It delegates morphology to `GermanicMorphology` and performs only
syntax-level assembly. The Batch 6 runtime contract lives one layer up in
the construction adapters; this file remains a narrow compatibility shim.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.core.domain.morphology.germanic import GermanicMorphology


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_gender(value: Any) -> str:
    raw = _clean_text(value).lower()
    if raw in {"m", "male", "masc", "masculine", "man"}:
        return "male"
    if raw in {"f", "female", "fem", "feminine", "woman"}:
        return "female"
    return raw


def _collapse_ws(text: str) -> str:
    text = " ".join(str(text).split())
    text = text.replace(" ,", ",").replace(" .", ".")
    text = text.replace(" ;", ";").replace(" :", ":")
    text = text.replace("( ", "(").replace(" )", ")")
    return text.strip()


def _compose_predicate(article: str, nationality: str, profession: str) -> str:
    return " ".join(part for part in (article, nationality, profession) if part)


def _select_copula_from_config(config: Mapping[str, Any], tense: str) -> str:
    """
    Fallback copula selector for old/new config shapes.

    Supported examples:

    Old-style:
        "verbs": {
          "copula": {
            "present": "ist",
            "past": "war"
          }
        }

    Matrix-style:
        "verbs": {
          "copula": {
            "present": {
              "3sg": "ist",
              "default": "ist"
            },
            "past": {
              "3sg": "war",
              "default": "war"
            },
            "zero_present": false
          }
        }
    """
    verbs_cfg = config.get("verbs", {}) or {}
    cop_cfg = verbs_cfg.get("copula", {}) or {}

    default_present = "is"
    default_past = "was"

    if isinstance(cop_cfg, str):
        return cop_cfg

    if not isinstance(cop_cfg, Mapping):
        return default_present if tense == "present" else default_past

    tense_cfg = cop_cfg.get(tense) or cop_cfg.get("present") or cop_cfg

    if isinstance(tense_cfg, str):
        return tense_cfg

    if isinstance(tense_cfg, Mapping):
        form = (
            tense_cfg.get("3sg")
            or tense_cfg.get("default")
            or next((v for v in tense_cfg.values() if isinstance(v, str) and v.strip()), None)
        )
        if form:
            return str(form)

    return default_present if tense == "present" else default_past


def _realize_copula(
    morph: GermanicMorphology,
    config: Mapping[str, Any],
    *,
    tense: str,
) -> str:
    """
    Prefer morphology-layer verb realization when available; otherwise fall back
    to raw config lookup.
    """
    if hasattr(morph, "realize_verb"):
        try:
            realized = morph.realize_verb(
                "be",
                {
                    "tense": tense,
                    "number": "sg",
                    "person": "3",
                },
            )
            realized = _clean_text(realized)
            if realized:
                return realized
        except Exception:
            pass

    return _select_copula_from_config(config, tense)


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def render_bio(
    name: str,
    gender: str,
    prof_lemma: str,
    nat_lemma: str,
    config: Mapping[str, Any],
) -> str:
    """
    Main entry point for Germanic biography sentences.

    Expected output examples:
        "Marie Curie war eine polnische Physikerin."
        "Marie Curie was a Polish physicist."
    """
    config = dict(config or {})
    morph = GermanicMorphology(config)

    subject_name = _clean_text(name)
    profession_lemma = _clean_text(prof_lemma)
    nationality_lemma = _clean_text(nat_lemma)
    norm_gender = _normalize_gender(gender)

    parts = morph.render_simple_bio_predicates(
        profession_lemma,
        nationality_lemma,
        norm_gender,
    )

    article = _clean_text(parts.get("article"))
    nationality = _clean_text(parts.get("nationality"))
    profession = _clean_text(parts.get("profession"))
    predicate = _compose_predicate(article, nationality, profession)

    bio_tense = _clean_text(config.get("syntax", {}).get("bio_default_tense")) or "past"
    copula = _realize_copula(morph, config, tense=bio_tense)

    structure = _clean_text(config.get("structure")) or "{name} {copula} {predicate}."

    values = _SafeFormatDict(
        name=subject_name,
        copula=copula,
        is_verb=copula,  # legacy placeholder
        predicate=predicate,
        article=article,
        nationality=nationality,
        profession=profession,
    )

    if "{" in structure and "}" in structure:
        sentence = structure.format_map(values)
    else:
        sentence = (
            structure.replace("{name}", subject_name)
            .replace("{copula}", copula)
            .replace("{is_verb}", copula)
            .replace("{predicate}", predicate)
            .replace("{article}", article)
            .replace("{nationality}", nationality)
            .replace("{profession}", profession)
        )

    return _collapse_ws(sentence)


__all__ = ["render_bio"]