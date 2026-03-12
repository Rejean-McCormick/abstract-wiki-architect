# app\adapters\engines\engines\bantu.py
"""
BANTU LANGUAGE ENGINE
---------------------
A data-driven renderer for Bantu languages (e.g. Swahili).

This module orchestrates sentence generation by:
1. Delegating noun-class agreement and copula selection to
   `app.core.domain.morphology.bantu.BantuMorphology`.
2. Handling sentence structure and final assembly.

Notes
-----
- For simple biography predicates, this engine assumes a human singular subject
  and therefore uses the morphology layer's configured default human noun class
  (commonly class 1).
- Natural gender is currently ignored for the default bio path, because Bantu
  agreement here is driven by noun class rather than masculine/feminine gender.
"""

from __future__ import annotations

try:
    # Actual repo path
    from app.core.domain.morphology.bantu import BantuMorphology
except ImportError:  # pragma: no cover - backward compatibility for old aliasing
    from morphology.bantu import BantuMorphology


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main entry point for Bantu biography rendering.

    Args:
        name (str): The subject's name.
        gender (str): Natural gender label. Currently unused for the basic
            human-singular bio path.
        prof_lemma (str): Profession lemma/stem.
        nat_lemma (str): Nationality/adjectival lemma/stem.
        config (dict): The merged configuration card for the language.

    Returns:
        str: The realized sentence.
    """
    # 1. Normalize inputs
    name = str(name or "").strip()
    prof_lemma = str(prof_lemma or "").strip()
    nat_lemma = str(nat_lemma or "").strip()

    # 2. Initialize morphology engine
    morph = BantuMorphology(config)

    # 3. Get inflected predicate pieces for the default human singular class
    #    Expected shape:
    #    {
    #        "class": <noun class>,
    #        "profession": <inflected profession>,
    #        "nationality": <inflected nationality>,
    #        "copula": <class-sensitive or default copula>,
    #    }
    bundle = morph.get_human_singular_bundle(prof_lemma, nat_lemma)

    copula = bundle.get("copula", "") or ""
    profession = bundle.get("profession", "") or ""
    nationality = bundle.get("nationality", "") or ""
    noun_class = bundle.get("class", morph.get_default_human_class())

    # Convenience combined predicate for templates that want a single slot.
    predicate = " ".join(part for part in (profession, nationality) if part)

    # 4. Assembly
    # Supports:
    # - modern placeholders: {copula}, {profession}, {nationality}, {predicate}
    # - legacy placeholder: {is_verb}
    # - debug / specialized templates: {class}, {noun_class}
    structure = config.get(
        "structure",
        "{name} {copula} {profession} {nationality}.",
    )

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{is_verb}", copula)  # legacy placeholder
    sentence = sentence.replace("{profession}", profession)
    sentence = sentence.replace("{nationality}", nationality)
    sentence = sentence.replace("{predicate}", predicate)
    sentence = sentence.replace("{class}", str(noun_class))
    sentence = sentence.replace("{noun_class}", str(noun_class))

    # 5. Cleanup
    sentence = " ".join(sentence.split())

    return sentence


__all__ = ["render_bio"]