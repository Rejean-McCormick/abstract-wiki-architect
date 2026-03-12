# app\adapters\engines\engines\romance.py
# engines\romance.py
"""
ROMANCE LANGUAGE ENGINE
-----------------------
A data-driven renderer for Romance languages (IT, ES, FR, PT, RO, CA, etc.).

This module orchestrates the generation of sentences by:
1. Delegating morphology to `app.core.domain.morphology.romance.RomanceMorphology`.
2. Handling sentence structure and assembly based on the per-language
   configuration card.
3. Preserving compatibility with both newer and legacy template placeholders.

The heavy lifting (gender inflection, article selection, phonetic
conditions, spacing rules) is done inside RomanceMorphology.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.core.domain.morphology.romance import RomanceMorphology


def _normalize_gender(gender: Any) -> Any:
    if isinstance(gender, str):
        g = gender.strip().lower()
        if g in {"m", "male", "masc", "masculine"}:
            return "male"
        if g in {"f", "female", "fem", "feminine"}:
            return "female"
        return g
    return gender


def _select_copula_from_config(config: Mapping[str, Any], tense: str) -> str:
    """
    Fallback copula selector for configs that expose the copula directly instead
    of via a morphology/verb helper.

    Supported shapes:

    1) Simple:
       "verbs": {
         "copula": {
           "present": "è",
           "past": "era"
         }
       }

    2) Person/number map:
       "verbs": {
         "copula": {
           "present": {
             "3sg": "est",
             "default": "est"
           }
         }
       }
    """
    verbs_cfg = config.get("verbs", {}) or {}
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


def _coerce_predicate_parts(parts: Any) -> tuple[str, str, str, str]:
    """
    Accept the current RomanceMorphology tuple contract while being tolerant of
    future dict-style family helpers.

    Expected current tuple contract:
        (article, profession, nationality, sep)
    """
    if isinstance(parts, tuple) and len(parts) == 4:
        article, profession, nationality, sep = parts
        return (
            article or "",
            profession or "",
            nationality or "",
            sep or "",
        )

    if isinstance(parts, dict):
        return (
            parts.get("article", "") or "",
            parts.get("profession", "") or "",
            parts.get("nationality", "") or "",
            parts.get("sep", " ") or "",
        )

    return "", "", "", " "


def render_bio(
    name: str,
    gender: str,
    prof_lemma: str,
    nat_lemma: str,
    config: Mapping[str, Any],
) -> str:
    """
    Main entry point for Romance-language biography sentences.

    Args:
        name:
            The subject's name (string as it should appear in the output).
        gender:
            Gender label (e.g. "Male", "Female", "M", "F").
        prof_lemma:
            Profession lemma in base form (typically masc. singular).
        nat_lemma:
            Nationality lemma in base form (typically masc. singular).
        config:
            The language-specific configuration card.

    Returns:
        A fully inflected biography sentence as a string.
    """
    # 1) Initialise morphology engine for this language.
    morph = RomanceMorphology(dict(config))
    norm_gender = _normalize_gender(gender)

    # 2) Let the morphology engine compute:
    #    - the correct indefinite article (with phonetic rules),
    #    - gendered profession,
    #    - gendered nationality,
    #    - the separator between article and profession ("" vs " ").
    raw_parts = morph.render_simple_bio_predicates(
        prof_lemma,
        nat_lemma,
        norm_gender,
    )
    article, profession, nationality, sep = _coerce_predicate_parts(raw_parts)

    # 3) Determine copula.
    # Romance bios are usually present-tense by default, but allow config override.
    syntax = config.get("syntax", {}) or {}
    bio_tense = (
        syntax.get("bio_tense")
        or syntax.get("bio_default_tense")
        or syntax.get("default_tense")
        or "present"
    )

    if hasattr(morph, "realize_verb"):
        copula = morph.realize_verb(
            "be",
            {
                "tense": bio_tense,
                "number": "sg",
                "person": "3",
            },
        )
    else:
        copula = _select_copula_from_config(config, bio_tense)

    # Prebuilt predicate helps newer templates stay simpler.
    article_phrase = f"{article}{sep}{profession}".strip() if profession else article.strip()
    predicate = " ".join(
        chunk for chunk in [article_phrase, nationality] if chunk
    ).strip()

    # 4) Assemble sentence using the language-specific structure template.
    #
    # Preferred modern template:
    #   "{name} {copula} {predicate}."
    #
    # Supported legacy placeholders:
    #   {is_verb}, {article}, {sep}, {profession}, {nationality}
    structure = config.get(
        "structure",
        "{name} {copula} {predicate}.",
    )

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{is_verb}", copula)  # legacy placeholder
    sentence = sentence.replace("{predicate}", predicate)
    sentence = sentence.replace("{article_phrase}", article_phrase)
    sentence = sentence.replace("{article}", article)
    sentence = sentence.replace("{sep}", sep)
    sentence = sentence.replace("{profession}", profession)
    sentence = sentence.replace("{nationality}", nationality)

    # 5) Light normalisation: collapse accidental double spaces and trim.
    sentence = " ".join(sentence.split())

    punctuation = syntax.get("punctuation", ".")
    if punctuation and not sentence.endswith(punctuation):
        sentence += punctuation

    return sentence