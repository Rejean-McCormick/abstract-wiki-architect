# app/adapters/engines/engines/analytic.py
# engines/analytic.py
"""
ANALYTIC LANGUAGE ENGINE
------------------------
A lightweight renderer for analytic / low-inflection languages.

This module stays intentionally simple:
1. It does little or no morphology itself.
2. It reads sentence structure from config.
3. It supports both newer `{copula}` / `{predicate}` templates and older
   split-slot templates such as `{profession}` and `{nationality}`.
"""

from __future__ import annotations


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main entry point for analytic biography rendering.

    Args:
        name (str): The subject's name.
        gender (str): Gender label, used only for article/copula selection if configured.
        prof_lemma (str): Profession base form.
        nat_lemma (str): Nationality base form.
        config (dict): Language/family configuration card.

    Returns:
        str: The rendered sentence.
    """
    config = config or {}

    norm_gender = _normalize_gender(gender)
    name = (name or "").strip()
    profession = (prof_lemma or "").strip()
    nationality = (nat_lemma or "").strip()

    article = _select_article(config, norm_gender)
    copula = _select_copula(config, norm_gender)

    structure = config.get(
        "structure",
        "{name} {copula} {article} {nationality} {profession}.",
    )

    predicate = _join_non_empty(article, nationality, profession)

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{is_verb}", copula)  # legacy placeholder
    sentence = sentence.replace("{article}", article)
    sentence = sentence.replace("{nationality}", nationality)
    sentence = sentence.replace("{profession}", profession)
    sentence = sentence.replace("{predicate}", predicate)

    sentence = " ".join(sentence.split())

    punctuation = config.get("syntax", {}).get("punctuation", ".")
    if sentence and punctuation and not sentence.endswith(punctuation):
        sentence += punctuation

    return sentence


def _normalize_gender(gender):
    if not isinstance(gender, str):
        return "default"

    g = gender.strip().lower()
    if g in {"m", "male", "masc", "masculine"}:
        return "male"
    if g in {"f", "female", "fem", "feminine"}:
        return "female"
    return g or "default"


def _select_article(config, norm_gender):
    articles_cfg = config.get("articles", {})

    if isinstance(articles_cfg, str):
        return articles_cfg.strip()

    indefinite = articles_cfg.get("indefinite", articles_cfg)

    if isinstance(indefinite, str):
        return indefinite.strip()

    return (
        indefinite.get(norm_gender)
        or indefinite.get("default")
        or indefinite.get("common")
        or ""
    ).strip()


def _select_copula(config, norm_gender):
    verbs_cfg = config.get("verbs", {})
    copula_cfg = verbs_cfg.get("copula")

    # Backward-compatible top-level fallback
    if copula_cfg is None:
        legacy = config.get("copula")
        if isinstance(legacy, str):
            return legacy.strip()
        if isinstance(legacy, dict):
            return (
                legacy.get(norm_gender)
                or legacy.get("default")
                or legacy.get("present")
                or ""
            ).strip()
        return ""

    if isinstance(copula_cfg, str):
        return copula_cfg.strip()

    syntax_cfg = config.get("syntax", {})
    tense = syntax_cfg.get("bio_default_tense", syntax_cfg.get("default_tense", "present"))

    tense_cfg = copula_cfg.get(tense, copula_cfg.get("default", copula_cfg))

    if isinstance(tense_cfg, str):
        return tense_cfg.strip()

    if isinstance(tense_cfg, dict):
        return (
            tense_cfg.get("3sg")
            or tense_cfg.get(norm_gender)
            or tense_cfg.get("default")
            or ""
        ).strip()

    return ""


def _join_non_empty(*parts):
    return " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip())