# app\adapters\engines\engines\isolating.py
# engines\isolating.py
"""
ISOLATING LANGUAGE ENGINE
-------------------------
A data-driven renderer for Isolating/Analytic languages (ZH, VI, TH).

This module orchestrates the generation of sentences by:
1. Delegating morphology (NP construction, classifiers) to `morphology.isolating`.
2. Handling sentence structure and assembly.
"""

from morphology.isolating import IsolatingMorphology


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Isolating Biographies.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female' (Used for pronoun selection, not inflection).
        prof_lemma (str): Profession (Invariant root).
        nat_lemma (str): Nationality (Invariant root).
        config (dict): The JSON configuration card.

    Returns:
        str: The constructed sentence.
    """
    # 1. Initialize Morphology Engine
    morph = IsolatingMorphology(config)

    # 2. Build Predicate NP
    # This handles:
    # - Adjective ordering (Nationality + Profession vs Profession + Nationality)
    # - Classifiers and Indefinite Articles (e.g., "yi ge ...")
    pred_features = {
        "adjectives": [nat_lemma],  # Nationality treated as adjective modifier
        "is_human": True,  # Biographies imply human subjects
        "number": "sg",
        "definiteness": "indef",  # Predicates are typically indefinite ("is a...")
    }

    predicate_np = morph.realize_noun_phrase(prof_lemma, pred_features)

    # 3. Get Copula
    # Isolating languages usually have an invariant copula defined in config
    copula = config.get("verbs", {}).get("copula", {}).get("default", "")

    # 4. Assembly
    # Default structure: "{name} {copula} {predicate}."
    # Note: We generally prefer using {predicate} here because the morphology layer
    # has already combined the profession and nationality correctly.
    structure = config.get("structure", "{name} {copula} {predicate}.")

    # If the structure uses old-style split tags, we try to support them strictly
    # by stripping particles from the predicate, but it's safer to rely on {predicate}.
    if "{predicate}" in structure:
        sentence = structure.replace("{name}", name)
        sentence = sentence.replace("{copula}", copula)
        sentence = sentence.replace("{predicate}", predicate_np)
    else:
        # Fallback: If template forces split tags (e.g. "{profession} {nationality}"),
        # we use raw lemmas, losing the classifier logic. This is a fallback.
        sentence = structure.replace("{name}", name)
        sentence = sentence.replace("{copula}", copula)
        sentence = sentence.replace("{profession}", prof_lemma)
        sentence = sentence.replace("{nationality}", nat_lemma)

    # Cleanup extra spaces
    sentence = " ".join(sentence.split())

    return sentence
