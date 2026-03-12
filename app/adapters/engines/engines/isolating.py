# app/adapters/engines/engines/isolating.py
"""
ISOLATING LANGUAGE ENGINE
-------------------------
Legacy family-level renderer for isolating / analytic languages
(e.g. ZH, VI, TH).

This module remains a compatibility renderer for direct bio generation.
It delegates noun-phrase shaping to the shared isolating morphology module
and handles only lightweight clause assembly here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.domain.morphology.isolating import IsolatingMorphology


def _normalize_surface(text: str, *, use_spaces: bool) -> str:
    """
    Normalize whitespace according to the language script policy.
    """
    if use_spaces:
        return " ".join(text.split())
    return "".join(text.split())


def _ensure_terminal_punctuation(text: str, config: Mapping[str, Any]) -> str:
    """
    Add terminal punctuation if the config expects it and the sentence
    does not already end with punctuation.
    """
    syntax = config.get("syntax", {}) if isinstance(config, Mapping) else {}
    punctuation = syntax.get("punctuation", ".")

    if not isinstance(punctuation, str) or not punctuation:
        return text

    if text.endswith(punctuation):
        return text

    if text.endswith((".", "。", "!", "?", "؟", "।", "॥")):
        return text

    return f"{text}{punctuation}"


def _select_copula(config: Mapping[str, Any]) -> str:
    """
    Resolve an invariant copula string from the language config.

    Supported shapes:
    - config["verbs"]["copula"] = "是"
    - config["verbs"]["copula"] = {"default": "是", "plain": "是"}
    - config["copula"] = "IS"   # legacy fallback
    """
    syntax = config.get("syntax", {}) if isinstance(config, Mapping) else {}
    verbs = config.get("verbs", {}) if isinstance(config, Mapping) else {}

    copula_cfg = verbs.get("copula", "") if isinstance(verbs, Mapping) else ""

    if isinstance(copula_cfg, str):
        return copula_cfg.strip()

    if isinstance(copula_cfg, Mapping):
        style = str(syntax.get("style", "") or "").strip()
        tense = str(syntax.get("bio_default_tense", "") or "").strip()

        for key in (style, tense, "default", "plain", "present"):
            value = copula_cfg.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    legacy = config.get("copula", "") if isinstance(config, Mapping) else ""
    if isinstance(legacy, str):
        return legacy.strip()

    return ""


def render_bio(
    name: str,
    gender: str,
    prof_lemma: str,
    nat_lemma: str,
    config: dict[str, Any],
) -> str:
    """
    Main entry point for isolating-language biographies.

    Args:
        name:
            The subject's surface name.
        gender:
            Ignored for morphology here; retained for call compatibility.
        prof_lemma:
            Profession lemma / invariant root.
        nat_lemma:
            Nationality / demonym lemma used as a modifier.
        config:
            Language configuration card.

    Returns:
        Fully assembled sentence string.
    """
    del gender  # compatibility-only parameter for the legacy engine surface

    safe_config: dict[str, Any] = dict(config or {})
    syntax = safe_config.get("syntax", {})
    use_spaces = bool(syntax.get("use_spaces", False))

    person_name = (name or "").strip()
    profession = (prof_lemma or "").strip()
    nationality = (nat_lemma or "").strip()

    morph = IsolatingMorphology(safe_config)

    # Core profession NP: keeps classifier / indefiniteness behavior even when
    # the template uses split placeholders instead of a single {predicate}.
    core_features: dict[str, Any] = {
        "is_human": True,
        "number": "sg",
        "definiteness": "indef",
    }
    profession_np = morph.realize_noun_core(profession, core_features) if profession else ""

    # Full predicate NP: nationality is treated as an adjective-like modifier.
    predicate_features = dict(core_features)
    if nationality:
        predicate_features["adjectives"] = [nationality]

    predicate_np = (
        morph.realize_noun_phrase(profession, predicate_features)
        if profession
        else nationality
    )

    copula = _select_copula(safe_config)

    structure = safe_config.get("structure", "{name} {copula} {predicate}")
    if not isinstance(structure, str) or not structure.strip():
        structure = "{name} {copula} {predicate}"

    sentence = structure
    replacements = {
        "{name}": person_name,
        "{copula}": copula,
        "{is_verb}": copula,          # legacy placeholder
        "{predicate}": predicate_np,  # preferred placeholder
        "{profession}": profession_np or profession,
        "{nationality}": nationality,
        "{article}": "",              # article/classifier are already inside NP logic
    }

    for placeholder, value in replacements.items():
        sentence = sentence.replace(placeholder, value)

    sentence = _normalize_surface(sentence, use_spaces=use_spaces)
    sentence = _ensure_terminal_punctuation(sentence, safe_config)

    return sentence


__all__ = ["render_bio"]