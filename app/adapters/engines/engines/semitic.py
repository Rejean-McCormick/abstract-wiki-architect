# app\adapters\engines\engines\semitic.py
# engines\semitic.py
"""
SEMITIC LANGUAGE ENGINE
-----------------------
A data-driven renderer for Semitic languages (AR, HE, AM, MT).

This module orchestrates the generation of sentences by:
1. Delegating morphology to the generic Semitic morphology engine.
2. Handling sentence structure and assembly.
3. Preserving Semitic-specific syntax defaults such as present-tense
   zero-copula nominal sentences.

Notes
-----
- Predicate nouns in biographies are typically indefinite.
- Nationality is commonly realized as an agreeing adjective or modifier.
- Present tense often uses a zero copula; past tense usually uses an
  overt copular verb when configured.
"""

from __future__ import annotations

from typing import Any, Mapping

try:
    from morphology.base import MorphRequest, MorphologyError
    from morphology.semitic import SemiticMorphologyEngine
except ImportError:  # pragma: no cover - compatibility with app package layout
    from app.core.domain.morphology.base import MorphRequest, MorphologyError
    from app.core.domain.morphology.semitic import SemiticMorphologyEngine


def _normalize_gender(gender: Any) -> str:
    """
    Normalize common gender labels to compact values typically used by
    Semitic morphology configs.
    """
    if not gender:
        return ""

    if isinstance(gender, str):
        g = gender.strip().lower()
        if g in {"m", "male", "masc", "masculine"}:
            return "m"
        if g in {"f", "female", "fem", "feminine"}:
            return "f"
        return g

    return str(gender).strip().lower()


def _get_language_code(config: Mapping[str, Any]) -> str:
    """
    Best-effort language-code lookup for morphology debug/provenance.
    """
    for key in ("language_code", "lang_code", "lang", "code"):
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _pick_gendered_value(value: Any, gender: str) -> str:
    """
    Read a possibly gender-indexed config bucket.

    Supports shapes like:
      {"m": "...", "f": "...", "default": "..."}
      {"male": "...", "female": "...", "default": "..."}
      "..."
    """
    if isinstance(value, str):
        return value

    if not isinstance(value, dict):
        return ""

    gender_keys = []
    if gender == "m":
        gender_keys = ["m", "male", "masc", "masculine"]
    elif gender == "f":
        gender_keys = ["f", "female", "fem", "feminine"]
    else:
        gender_keys = [gender]

    for key in gender_keys:
        form = value.get(key)
        if isinstance(form, str) and form:
            return form

    default = value.get("default")
    if isinstance(default, str):
        return default

    for candidate in value.values():
        if isinstance(candidate, str) and candidate:
            return candidate

    return ""


def _select_copula_from_config(config: Mapping[str, Any], tense: str, gender: str) -> str:
    """
    Fallback copula selector for older Semitic language cards.

    Supported shapes:
      verbs.present_copula = {"m": "...", "f": "..."}
      verbs.past_copula = {"m": "...", "f": "..."}
      verbs.copula = {
          "present": {"m": "...", "f": "...", "default": ""},
          "past": {"m": "...", "f": "...", "default": "..."},
          "zero_present": true
      }
    """
    syntax = config.get("syntax", {})
    verbs = config.get("verbs", {})

    # Present-tense nominal sentences default to zero copula unless the card
    # explicitly provides a present copula form.
    if tense == "present":
        zero_present = syntax.get(
            "zero_copula_present",
            verbs.get("copula", {}).get("zero_present", True)
            if isinstance(verbs.get("copula"), dict)
            else True,
        )
        present_cfg = verbs.get("present_copula")
        if present_cfg is None and isinstance(verbs.get("copula"), dict):
            present_cfg = verbs["copula"].get("present")

        if zero_present and not present_cfg:
            return ""

        return _pick_gendered_value(present_cfg, gender)

    if tense == "past":
        past_cfg = verbs.get("past_copula")
        if past_cfg is None and isinstance(verbs.get("copula"), dict):
            past_cfg = verbs["copula"].get("past")
        return _pick_gendered_value(past_cfg, gender)

    # Any non-standard tense falls back to explicit config only.
    if isinstance(verbs.get("copula"), dict):
        tense_cfg = verbs["copula"].get(tense)
        return _pick_gendered_value(tense_cfg, gender)

    return ""


def _inflect_or_passthrough(
    morph: SemiticMorphologyEngine,
    lemma: str,
    pos: str,
    features: Mapping[str, str],
) -> str:
    """
    Ask morphology for an inflected form; if no rule matches, preserve the
    original lemma rather than failing generation.
    """
    if not lemma:
        return ""

    try:
        result = morph.inflect(
            MorphRequest(
                lemma=lemma,
                pos=pos,
                features=features,
                language_code=morph.language_code,
            )
        )
        return result.surface or lemma
    except (MorphologyError, KeyError, ValueError):
        return lemma


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Semitic biographies.

    Args:
        name (str): The subject's name.
        gender (str): Gender label such as 'Male' / 'Female'.
        prof_lemma (str): Profession lemma (typically masculine singular/base).
        nat_lemma (str): Nationality/demonym lemma (typically masculine singular/base).
        config (dict): The JSON configuration card.

    Returns:
        str: The fully realized sentence.
    """
    # 1. Normalize Inputs
    norm_gender = _normalize_gender(gender)
    profession_lemma = (prof_lemma or "").strip()
    nationality_lemma = (nat_lemma or "").strip()

    # 2. Initialize Morphology Engine
    morph = SemiticMorphologyEngine(
        language_code=_get_language_code(config),
        config=config,
    )

    syntax = config.get("syntax", {})
    predicate_case = syntax.get("predicate_case", "nom")
    predicate_definiteness = syntax.get("predicate_definiteness", "indef")
    nationality_pos = syntax.get("nationality_pos", "ADJ")

    # 3. Realize Predicate Components
    #
    # Profession is treated as a predicate noun.
    # Nationality is usually an adjective/modifier agreeing with the predicate,
    # but cards may override `nationality_pos` to "NOUN" if needed.
    base_features = {
        "number": "sg",
        "definiteness": predicate_definiteness,
        "case": predicate_case,
    }
    if norm_gender:
        base_features["gender"] = norm_gender

    profession = _inflect_or_passthrough(
        morph,
        profession_lemma,
        "NOUN",
        base_features,
    )

    nationality = _inflect_or_passthrough(
        morph,
        nationality_lemma,
        nationality_pos,
        base_features,
    )

    # 4. Get Copula
    # Semitic biography defaults lean toward present-tense nominal sentences.
    bio_tense = syntax.get