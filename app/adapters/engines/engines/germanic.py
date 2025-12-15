# engines\germanic.py
"""
GERMANIC LANGUAGE ENGINE
------------------------
A data-driven renderer for Germanic languages (EN, DE, NL, SV, DA, NO).

This module orchestrates the generation of sentences by:
1. Delegating morphology to `morphology.germanic.GermanicMorphology`.
2. Handling sentence structure and assembly, using data from:
   - family matrix:  data/morphology_configs/germanic_grammar_matrix.json
   - language card:  data/germanic/<lang>.json
"""

from morphology.germanic import GermanicMorphology


def _select_copula_from_config(config, tense: str) -> str:
    """
    Fallback copula selector, used if the morphology layer does not
    provide `realize_verb`. It understands both the old, simpler
    per-language cards and the new grammar-matrix style.

    Supported shapes:

    1) Old-style (string per tense):
       "verbs": {
         "copula": {
           "present": "ist",
           "past": "war"
         }
       }

    2) Matrix-style (person/number table):
       "verbs": {
         "copula": {
           "present": {
             "3sg": "ist",
             "default": "ist"
           },
           "past": {
             "3sg": "war",
             "default": "war"
           },
           "zero_present": false
         }
       }
    """
    verbs_cfg = config.get("verbs", {})
    cop_cfg = verbs_cfg.get("copula", {})

    # default if everything fails
    default_present = "is"
    default_past = "was"

    if isinstance(cop_cfg, str):
        # Extremely old / simplified form: single string
        return cop_cfg

    if not isinstance(cop_cfg, dict):
        # No usable config, fall back to English-ish defaults
        return default_present if tense == "present" else default_past

    # Try to get the tense bucket (present/past), falling back to present
    tense_cfg = cop_cfg.get(tense) or cop_cfg.get("present") or cop_cfg

    if isinstance(tense_cfg, str):
        # Old-style: "present": "ist"
        return tense_cfg

    if isinstance(tense_cfg, dict):
        # Matrix-style: pick 3sg, default, or first available form
        form = (
            tense_cfg.get("3sg")
            or tense_cfg.get("default")
            or (next(iter(tense_cfg.values())) if tense_cfg else None)
        )
        if form:
            return form

    # Last-resort fallback
    return default_present if tense == "present" else default_past


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Germanic Biographies.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female' (case-insensitive; other values passed through).
        prof_lemma (str): The profession (e.g., "Lehrer" / "teacher"), base lemma.
        nat_lemma (str): The nationality adjective (e.g., "deutsch" / "German"), base lemma.
        config (dict): The merged configuration card for the specific language
                       (family matrix + language card).

    Returns:
        str: The fully inflected sentence, e.g.:
             "Marie Curie war eine polnische Physikerin."
             "Marie Curie was a Polish physicist."
    """
    # 1. Initialize Morphology Engine
    morph = GermanicMorphology(config)

    # Normalize gender a bit for safety; morphology layer can refine this further.
    if isinstance(gender, str):
        g = gender.strip().lower()
        if g in {"m", "male", "masc", "masculine"}:
            norm_gender = "male"
        elif g in {"f", "female", "fem", "feminine"}:
            norm_gender = "female"
        else:
            norm_gender = g
    else:
        norm_gender = gender

    # 2. Get Predicate Components (Profession, Nationality, Article)
    # This handles gender inflection, adjective declension, and article selection.
    # Expected return shape (dict):
    #   {
    #     "profession": <inflected profession>,
    #     "nationality": <inflected nationality>,
    #     "article": <indefinite/definite article or "">
    #   }
    parts = morph.render_simple_bio_predicates(prof_lemma, nat_lemma, norm_gender)

    article = parts.get("article", "") or ""
    nationality = parts.get("nationality", "") or ""
    profession = parts.get("profession", "") or ""

    # 3. Get Verb (Copula)
    # Default to the language's configured tense for bios; if missing, fall back to "past".
    bio_tense = config.get("syntax", {}).get("bio_default_tense", "past")

    if hasattr(morph, "realize_verb"):
        # Use the unified verb API if available (preferred).
        copula = morph.realize_verb(
            "be",
            {
                "tense": bio_tense,
                "number": "sg",
                "person": "3",
            },
        )
    else:
        # Fallback: read directly from config (supports old/new copula encodings).
        copula = _select_copula_from_config(config, bio_tense)

    # 4. Assembly
    #
    # We support both the new `{copula}` placeholder and the legacy `{is_verb}` one.
    # Default template if none is provided:
    #   "{name} {copula} {article} {nationality} {profession}."
    structure = config.get(
        "structure",
        "{name} {copula} {article} {nationality} {profession}.",
    )

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{is_verb}", copula)  # legacy placeholder
    sentence = sentence.replace("{article}", article)
    sentence = sentence.replace("{nationality}", nationality)
    sentence = sentence.replace("{profession}", profession)

    # Cleanup extra whitespace (e.g., if article is empty)
    sentence = " ".join(sentence.split())

    return sentence
