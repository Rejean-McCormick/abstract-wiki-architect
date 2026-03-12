# app/adapters/engines/engines/slavic.py
"""
SLAVIC LANGUAGE ENGINE
----------------------
Compatibility renderer for Slavic languages (RU, PL, CS, UK, SR, HR, BG).

This module stays on the legacy family-engine surface:

    render_bio(name, gender, prof_lemma, nat_lemma, config) -> str

It delegates morphology to `SlavicMorphology` and performs only
syntax-level assembly. The Batch 6 runtime contract lives one layer up in
the construction adapters; this file remains a narrow compatibility shim.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.core.domain.morphology.slavic import SlavicMorphology


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


def _compose_predicate(nationality: str, profession: str) -> str:
    return " ".join(part for part in (nationality, profession) if part)


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
    Main entry point for Slavic biography sentences.

    Expected output examples:
        "Maria Skłodowska była polską fizyczką."
        "Мария Кюри была польской физиком."
    """
    config = dict(config or {})
    morph = SlavicMorphology(config)

    subject_name = _clean_text(name)
    profession_lemma = _clean_text(prof_lemma)
    nationality_lemma = _clean_text(nat_lemma)
    norm_gender = _normalize_gender(gender)

    # SlavicMorphology is responsible for:
    # - noun/adjective gender derivation
    # - predicative case inflection
    # - past-tense copula selection
    parts = morph.render_simple_bio_predicates(
        profession_lemma,
        nationality_lemma,
        norm_gender,
    )

    profession = _clean_text(parts.get("profession"))
    nationality = _clean_text(parts.get("nationality"))
    copula = _clean_text(parts.get("copula"))
    predicate_case = _clean_text(parts.get("case"))
    predicate = _compose_predicate(nationality, profession)

    # Support both modern and legacy placeholders.
    structure = _clean_text(config.get("structure")) or "{name} {copula} {predicate}."

    values = _SafeFormatDict(
        name=subject_name,
        verb=copula,          # legacy placeholder
        copula=copula,
        predicate=predicate,
        nationality=nationality,
        profession=profession,
        case=predicate_case,
    )

    if "{" in structure and "}" in structure:
        sentence = structure.format_map(values)
    else:
        sentence = (
            structure.replace("{name}", subject_name)
            .replace("{verb}", copula)
            .replace("{copula}", copula)
            .replace("{predicate}", predicate)
            .replace("{nationality}", nationality)
            .replace("{profession}", profession)
            .replace("{case}", predicate_case)
        )

    return _collapse_ws(sentence)


__all__ = ["render_bio"]