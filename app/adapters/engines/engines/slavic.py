# engines\slavic.py
"""
SLAVIC LANGUAGE ENGINE
----------------------
A data-driven renderer for Slavic languages (RU, PL, CS, UK, SR, HR, BG).

This module orchestrates the generation of sentences by:
1. Delegating morphology to `morphology.slavic.SlavicMorphology`.
2. Handling sentence structure and assembly.
"""

from morphology.slavic import SlavicMorphology


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Slavic Biographies.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female'.
        prof_lemma (str): Profession in Nominative Singular (Dictionary form).
        nat_lemma (str): Nationality in Nominative Singular.
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """
    # 1. Initialize Morphology Engine
    morph = SlavicMorphology(config)

    # 2. Get Predicate Components (Profession, Nationality, Copula, Case)
    # This handles gender inflection (feminization), case declension (e.g. Instrumental),
    # and copula selection (gendered past tense or zero present).
    parts = morph.render_simple_bio_predicates(prof_lemma, nat_lemma, gender)

    # 3. Assembly
    # Structure typically uses the copula in past tense, or zero in present tense (Russian)
    structure = config.get("structure", "{name} {verb} {nationality} {profession}.")

    # Map morphology outputs to template placeholders
    # Note: 'verb' in template usually maps to the copula
    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{verb}", parts["copula"])
    sentence = sentence.replace("{copula}", parts["copula"])  # Support both keys
    sentence = sentence.replace("{nationality}", parts["nationality"])
    sentence = sentence.replace("{profession}", parts["profession"])

    # Cleanup extra spaces (e.g. if verb is empty in Russian Present Tense)
    sentence = " ".join(sentence.split())

    return sentence
