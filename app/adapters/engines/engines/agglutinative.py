# app\adapters\engines\engines\agglutinative.py
"""
AGGLUTINATIVE LANGUAGE ENGINE
-----------------------------
A data-driven renderer for agglutinative languages (TR, HU, FI, ET).

This module orchestrates the generation of sentences by:
1. Delegating suffix selection / harmony logic to
   `morphology.agglutinative.AgglutinativeMorphology`.
2. Handling sentence structure and assembly.
3. Preserving the legacy `render_bio(...)` engine surface used by the
   family adapter/runtime.

Notes
-----
- Natural gender is usually not grammatical in this family, so `gender`
  is accepted for compatibility but normally ignored.
- Copular meaning is typically realized inside the predicative noun form,
  not as a free-standing verb token.
"""

from __future__ import annotations

from typing import Any, Dict

from morphology.agglutinative import AgglutinativeMorphology


def render_bio(
    name: str,
    gender: str,
    prof_lemma: str,
    nat_lemma: str,
    config: Dict[str, Any],
) -> str:
    """
    Main entry point for agglutinative biography sentences.

    Args:
        name:
            The subject's name.
        gender:
            Compatibility-only input. Usually ignored for grammar in this family.
        prof_lemma:
            Profession/root noun (dictionary form).
        nat_lemma:
            Nationality/root modifier (dictionary form).
        config:
            Per-language configuration card.

    Returns:
        Fully assembled sentence.
    """
    # 1. Normalize inputs
    del gender  # accepted for compatibility with the shared family-engine surface

    name = str(name or "").strip()
    prof_lemma = str(prof_lemma or "").strip()
    nat_lemma = str(nat_lemma or "").strip()
    config = config or {}

    # 2. Delegate morphology
    morph = AgglutinativeMorphology(config)
    parts = morph.render_simple_predicate(prof_lemma, nat_lemma)

    profession = (parts.get("profession") or "").strip()
    nationality = (parts.get("nationality") or "").strip()

    # Build a combined predicate for templates that prefer a single slot.
    # In simple agglutinative bios the nationality typically stays bare
    # and modifies the profession block.
    predicate = " ".join(part for part in (nationality, profession) if part).strip()

    # 3. Assembly
    #
    # Preferred default stays compatible with the current file:
    #   "{name} {nationality} {profession}."
    #
    # We also support newer templates that use {predicate}, and tolerate
    # legacy placeholders that are irrelevant for this family runtime.
    structure = config.get("structure", "{name} {nationality} {profession}.")

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{predicate}", predicate)
    sentence = sentence.replace("{nationality}", nationality)
    sentence = sentence.replace("{profession}", profession)

    # Agglutinative predicate copula is usually already fused into
    # `profession`, so standalone copula slots collapse to empty.
    sentence = sentence.replace("{copula}", "")
    sentence = sentence.replace("{copula_suffix}", "")
    sentence = sentence.replace("{is_verb}", "")
    sentence = sentence.replace("{article}", "")

    # 4. Cleanup
    sentence = " ".join(sentence.split())

    punctuation = config.get("syntax", {}).get("punctuation", ".")
    if sentence and not sentence.endswith(punctuation):
        if sentence[-1] not in ".!?。":
            sentence += punctuation

    return sentence