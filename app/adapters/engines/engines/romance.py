# engines\romance.py
"""
ROMANCE LANGUAGE ENGINE
-----------------------
A data-driven renderer for Romance languages (IT, ES, FR, PT, RO, CA, etc.).

This module orchestrates the generation of sentences by:
1. Delegating morphology to `morphology.romance.RomanceMorphology`.
2. Handling sentence structure and assembly based on the per-language
   configuration card in data/romance/*.json.

The heavy lifting (gender inflection, article selection, phonetic
conditions, spacing rules) is done inside RomanceMorphology.
"""

from __future__ import annotations

from typing import Dict, Any

from morphology.romance import RomanceMorphology


def render_bio(
    name: str,
    gender: str,
    prof_lemma: str,
    nat_lemma: str,
    config: Dict[str, Any],
) -> str:
    """
    Main entry point for Romance-language biography sentences.

    Args:
        name:
            The subject's name (string as it should appear in the output).
        gender:
            Gender label (e.g. "Male", "Female", "M", "F").
            Normalisation is handled inside RomanceMorphology.
        prof_lemma:
            Profession lemma in base form (typically masc. singular).
        nat_lemma:
            Nationality lemma in base form (typically masc. singular).
        config:
            The language-specific configuration card loaded from
            data/romance/<lang_code>.json.

    Returns:
        A fully inflected biography sentence as a string.
    """
    # 1) Initialise morphology engine for this language
    morph = RomanceMorphology(config)

    # 2) Let the morphology engine compute:
    #    - the correct indefinite article (with phonetic rules),
    #    - gendered profession,
    #    - gendered nationality,
    #    - the separator between article and profession ("" vs " ").
    article, profession, nationality, sep = morph.render_simple_bio_predicates(
        prof_lemma,
        nat_lemma,
        gender,
    )

    # 3) Assemble sentence using the language-specific structure template.
    #
    # Examples of structures in config:
    #   "{name} è {article}{sep}{profession} {nationality}."
    #   "{name} es {article} {profession} {nationality}."
    #
    # We always provide the same set of keys; if the template omits some
    # (e.g. {sep}), they are simply unused.
    structure = config.get(
        "structure",
        "{name} {article}{sep}{profession} {nationality}.",
    )

    sentence = structure.format(
        name=name,
        article=article,
        sep=sep,
        profession=profession,
        nationality=nationality,
    )

    # 4) Light normalisation: collapse accidental double spaces and trim.
    sentence = " ".join(sentence.split())

    return sentence
