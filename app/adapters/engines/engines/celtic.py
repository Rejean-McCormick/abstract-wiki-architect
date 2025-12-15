# engines\celtic.py
"""
CELTIC LANGUAGE ENGINE
----------------------
A data-driven renderer for Celtic languages (CY, GA, GD, KW, BR).

This module orchestrates the generation of sentences by:
1. Delegating morphology to `morphology.celtic.CelticMorphology`.
2. Handling sentence structure and assembly.
"""

from morphology.celtic import CelticMorphology


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Celtic Biographies.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female'.
        prof_lemma (str): Profession in radical/base form (e.g. "athro").
        nat_lemma (str): Nationality in radical/base form (e.g. "Cymreig").
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """
    # 1. Initialize Morphology Engine
    morph = CelticMorphology(config)

    # 2. Get Predicate Components
    # This handles gender inflection, mutations, and copula selection.
    parts = morph.render_simple_bio_predicates(prof_lemma, nat_lemma, gender)

    # 3. Get Particle (Syntactic glue, e.g. Welsh "yn")
    # The morphology engine applies the mutation caused by this particle,
    # but the particle itself is placed by the syntax engine.
    syntax = config.get("syntax", {})
    particle = syntax.get("predicative_particle", "")

    # 4. Assembly
    structure = config.get(
        "structure",
        "{copula} {name} {particle} {profession} {nationality}.",
    )

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{copula}", parts["copula"])
    sentence = sentence.replace("{particle}", particle)
    sentence = sentence.replace("{profession}", parts["profession"])
    sentence = sentence.replace("{nationality}", parts["nationality"])

    # Sanity cleanup
    sentence = " ".join(sentence.split())

    return sentence
