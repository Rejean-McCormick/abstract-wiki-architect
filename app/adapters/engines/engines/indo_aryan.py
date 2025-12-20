# app\adapters\engines\engines\indo_aryan.py
# engines\indo_aryan.py
"""
INDO-ARYAN LANGUAGE ENGINE
--------------------------
A data-driven renderer for Indo-Aryan languages (HI, BN, UR, PA, MR).

This module orchestrates the generation of sentences by:
1. Delegating morphology to `morphology.indo_aryan.IndoAryanMorphology`.
2. Handling sentence structure and assembly.
"""

from morphology.indo_aryan import IndoAryanMorphology


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Indo-Aryan Biographies.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female'.
        prof_lemma (str): Profession (Masculine Singular Base).
        nat_lemma (str): Nationality (Masculine Singular Base).
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """
    # 1. Initialize Morphology Engine
    morph = IndoAryanMorphology(config)

    # 2. Get Predicate Components
    # This handles gender inflection for nouns/adjectives and copula selection
    # (including zero copula logic).
    parts = morph.render_simple_bio_predicates(prof_lemma, nat_lemma, gender)

    # 3. Assembly
    structure = config.get("structure", "{name} {nationality} {profession} {copula}.")

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{nationality}", parts["nationality"])
    sentence = sentence.replace("{profession}", parts["profession"])
    sentence = sentence.replace("{copula}", parts["copula"])

    # Clean up double spaces (vital for Zero Copula languages)
    sentence = " ".join(sentence.split())

    # Ensure final punctuation (some scripts might use Danda '?')
    punctuation = config.get("syntax", {}).get("punctuation", ".")
    if not sentence.endswith(punctuation):
        sentence += punctuation

    return sentence
