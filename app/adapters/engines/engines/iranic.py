# engines\iranic.py
"""
IRANIC LANGUAGE ENGINE
----------------------
A data-driven renderer for Iranic languages (FA, PS, KU, TG).

This module orchestrates the generation of sentences by:
1. Delegating morphology (Ezafe, gender, indefiniteness) to `morphology.iranic.IranicMorphology`.
2. Handling sentence structure and assembly.
"""

from morphology.iranic import IranicMorphology


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Iranic Biographies.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female'.
        prof_lemma (str): Profession (Base form).
        nat_lemma (str): Nationality (Base form).
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """
    # 1. Initialize Morphology Engine
    morph = IranicMorphology(config)

    # 2. Get Predicate Components
    # This handles:
    # - Gender inflection (if applicable, e.g. Pashto)
    # - Ezafe construction (linking Profession to Nationality)
    # - Indefinite marking (e.g. Persian 'Ya-ye Vahdat')
    # - Copula selection
    parts = morph.render_simple_bio_predicates(prof_lemma, nat_lemma, gender)

    # 3. Assembly
    structure = config.get("structure", "{name} {predicate} {copula}.")

    # The morphology engine returns 'noun_phrase' which contains the
    # fully linked "Profession-e Nationality" structure (plus indefinite markers).
    # We map this to {predicate} or {profession} depending on the template.

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{predicate}", parts["noun_phrase"])

    # Fallback replacements if the structure template uses specific tags
    # Note: parts['noun_phrase'] is usually the whole block "X-e Y-i"
    sentence = sentence.replace("{profession}", parts["noun_phrase"])
    sentence = sentence.replace("{nationality}", "")  # Consumed by noun_phrase

    sentence = sentence.replace("{copula}", parts["copula"])

    # Cleanup extra spaces
    sentence = " ".join(sentence.split())

    return sentence
