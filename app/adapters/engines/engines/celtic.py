# app\adapters\engines\engines\celtic.py
# engines\celtic.py
"""
CELTIC LANGUAGE ENGINE
----------------------
A data-driven renderer for Celtic languages (CY, GA, GD, KW, BR).

This module orchestrates the generation of sentences by:
1. Delegating morphology to `app.core.domain.morphology.celtic.CelticMorphology`.
2. Handling sentence structure and assembly.
3. Preserving compatibility with both newer and legacy template placeholders.
"""

from __future__ import annotations

from app.core.domain.morphology.celtic import CelticMorphology


def _normalize_gender(gender):
    if isinstance(gender, str):
        g = gender.strip().lower()
        if g in {"m", "male", "masc", "masculine"}:
            return "male"
        if g in {"f", "female", "fem", "feminine"}:
            return "female"
        return g
    return gender


def _select_copula_from_config(config, tense: str) -> str:
    """
    Fallback copula selector for configs that expose the copula directly instead
    of relying on the morphology helper.

    Supported shapes:

    1) Simple:
       "verbs": {
         "copula": {
           "present": "yw",
           "past": "oedd"
         }
       }

    2) Person/number map:
       "verbs": {
         "copula": {
           "present": {
             "3sg": "yw",
             "default": "yw"
           }
         }
       }
    """
    verbs_cfg = config.get("verbs", {})
    cop_cfg = verbs_cfg.get("copula", {})

    if isinstance(cop_cfg, str):
        return cop_cfg

    if not isinstance(cop_cfg, dict):
        return ""

    tense_cfg = cop_cfg.get(tense) or cop_cfg.get("present") or cop_cfg

    if isinstance(tense_cfg, str):
        return tense_cfg

    if isinstance(tense_cfg, dict):
        form = (
            tense_cfg.get("3sg")
            or tense_cfg.get("default")
            or (next(iter(tense_cfg.values())) if tense_cfg else None)
        )
        if form:
            return form

    return ""


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Celtic Biographies.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female' (case-insensitive; other values passed through).
        prof_lemma (str): Profession in radical/base form (e.g. "athro").
        nat_lemma (str): Nationality in radical/base form (e.g. "Cymreig").
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """
    # 1. Initialize Morphology Engine
    morph = CelticMorphology(config)
    norm_gender = _normalize_gender(gender)

    # 2. Get Predicate Components
    # This handles gender inflection and configured initial mutations.
    parts = morph.render_simple_bio_predicates(prof_lemma, nat_lemma, norm_gender)

    profession = parts.get("profession", "") or ""
    nationality = parts.get("nationality", "") or ""

    # 3. Get Copula / Particle
    syntax = config.get("syntax", {})
    particle = syntax.get("predicative_particle", "") or ""

    bio_tense = (
        syntax.get("bio_tense")
        or syntax.get("bio_default_tense")
        or parts.get("tense")
        or "present"
    )

    copula = parts.get("copula", "") or ""
    if not copula and hasattr(morph, "select_copula"):
        copula = morph.select_copula(bio_tense, person=3, number="sg")
    if not copula:
        copula = _select_copula_from_config(config, bio_tense)

    # Prebuilt predicate is safer for new templates.
    predicate = " ".join(
        chunk for chunk in [particle, profession, nationality] if chunk
    ).strip()

    # 4. Assembly
    #
    # Preferred modern template:
    #   "{copula} {name} {predicate}."
    #
    # Supported legacy placeholders:
    #   {particle}, {profession}, {nationality}, {is_verb}
    structure = config.get(
        "structure",
        "{copula} {name} {predicate}.",
    )

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{is_verb}", copula)  # legacy placeholder
    sentence = sentence.replace("{predicate}", predicate)
    sentence = sentence.replace("{particle}", particle)
    sentence = sentence.replace("{profession}", profession)
    sentence = sentence.replace("{nationality}", nationality)

    # Cleanup
    sentence = " ".join(sentence.split())

    punctuation = syntax.get("punctuation", ".")
    if punctuation and not sentence.endswith(punctuation):
        sentence += punctuation

    return sentence