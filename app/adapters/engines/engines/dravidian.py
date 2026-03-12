# app\adapters\engines\engines\dravidian.py
# engines\dravidian.py
"""
DRAVIDIAN LANGUAGE ENGINE
-------------------------
A data-driven renderer for Dravidian languages (TA, ML, TE, KN).

This module orchestrates the generation of sentences by:
1. Delegating morphology (copular suffixes, light sandhi, agreement) to
   `morphology.dravidian.DravidianMorphology`.
2. Handling sentence structure and assembly.

Notes
-----
- Dravidian biography predicates are often realized with a predicative noun
  carrying the copular/agreement suffix.
- Nationality is typically passed through as a bare modifier; constructions or
  templates decide ordering.
- Zero-copula languages/templates are supported naturally because the
  morphology layer may return the bare noun when no copular suffix is configured.
"""

from __future__ import annotations

try:
    from morphology.dravidian import DravidianMorphology
except ImportError:  # pragma: no cover - compatibility with app package layout
    from app.core.domain.morphology.dravidian import DravidianMorphology


def _normalize_gender(gender) -> str:
    """
    Normalize common gender labels to the compact forms expected by morphology.
    """
    if not gender:
        return ""

    if isinstance(gender, str):
        g = gender.strip().lower()
        if g in {"m", "male", "masc", "masculine"}:
            return "male"
        if g in {"f", "female", "fem", "feminine"}:
            return "female"
        if g in {"n", "neuter", "neutral"}:
            return "neut"
        return g

    return str(gender).strip().lower()


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Dravidian Biographies.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female' (case-insensitive; other values passed through).
        prof_lemma (str): Profession (base lemma).
        nat_lemma (str): Nationality/demonym modifier (base lemma).
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """
    # 1. Initialize Morphology Engine
    morph = DravidianMorphology(config)

    norm_gender = _normalize_gender(gender)
    profession_lemma = (prof_lemma or "").strip()
    nationality_lemma = (nat_lemma or "").strip()

    # 2. Ask morphology for the predicative profession form.
    # DravidianMorphology already handles:
    # - copular / agreement suffixes
    # - light configurable sandhi
    # - zero-copula fallback when no suffix is configured
    bio_tense = config.get("syntax", {}).get("bio_default_tense", "past")

    parts = morph.render_simple_bio_predicates(
        profession_lemma,
        nationality_lemma or None,
        person=3,
        number="sg",
        gender=norm_gender or None,
        tense=bio_tense,
    )

    profession = parts.get("profession", "") or ""
    nationality = parts.get("nationality", "") or ""

    # Some templates may prefer a single predicate slot.
    predicate = " ".join(part for part in (nationality, profession) if part)

    # 3. Assembly
    #
    # Default keeps nationality separate because the morphology layer deliberately
    # leaves it as a bare modifier while inflecting only the predicative noun.
    structure = config.get(
        "structure",
        "{name} {nationality} {profession}.",
    )

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{predicate}", predicate)
    sentence = sentence.replace("{nationality}", nationality)
    sentence = sentence.replace("{profession}", profession)

    # Legacy placeholders: older templates may still contain these.
    # In the newer morphology-driven path, the copular material is usually already
    # attached to `profession`, so these collapse to empty strings.
    sentence = sentence.replace("{copula}", "")
    sentence = sentence.replace("{is_verb}", "")
    sentence = sentence.replace("{copula_suffix}", "")

    # Cleanup extra whitespace (important for zero-copula languages/templates)
    sentence = " ".join(sentence.split())

    # Align with neighboring engines that honor configurable punctuation.
    punctuation = config.get("syntax", {}).get("punctuation", ".")
    if punctuation and not sentence.endswith(punctuation):
        sentence += punctuation

    return sentence