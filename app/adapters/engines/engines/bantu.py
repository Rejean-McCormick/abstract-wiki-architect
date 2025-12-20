# app\adapters\engines\engines\bantu.py
# engines\bantu.py
"""
BANTU LANGUAGE ENGINE
---------------------
A data-driven renderer for Bantu languages (e.g. Swahili).

This module orchestrates the generation of sentences by:
1. Delegating morphology to `morphology.bantu.BantuMorphology`.
2. Handling sentence structure and assembly.
"""

from morphology.bantu import BantuMorphology


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Bantu Biographies.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female' (Currently unused/ignored for human class).
        prof_lemma (str): Profession lemma.
        nat_lemma (str): Nationality lemma.
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """
    # 1. Initialize Morphology Engine
    morph = BantuMorphology(config)

    # 2. Get Predicate Components
    # This helper handles noun class selection (usually class 1 for humans),
    # prefix application, vowel harmony, and copula selection.
    bundle = morph.get_human_singular_bundle(prof_lemma, nat_lemma)

    # 3. Assembly
    structure = config.get("structure", "{name} {copula} {profession} {nationality}.")

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{copula}", bundle["copula"])
    sentence = sentence.replace("{profession}", bundle["profession"])
    sentence = sentence.replace("{nationality}", bundle["nationality"])

    # Sanity cleanup
    sentence = " ".join(sentence.split())

    return sentence
