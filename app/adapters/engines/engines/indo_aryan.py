# app/adapters/engines/engines/indo_aryan.py
"""
INDO-ARYAN LANGUAGE ENGINE
--------------------------
A data-driven renderer for Indo-Aryan languages (HI, BN, UR, PA, MR).

This module orchestrates the generation of sentences by:
1. Delegating morphology to `app.core.domain.morphology.indo_aryan.IndoAryanMorphology`.
2. Handling sentence structure and assembly.
"""

from app.core.domain.morphology.indo_aryan import IndoAryanMorphology


def _select_copula_from_config(config, gender: str) -> str:
    """
    Fallback copula selector for older or partial configs.

    Supported shapes:

    1) String:
       "verbs": {"copula": "hai"}

    2) Dict with formality / gender / default:
       "verbs": {
         "copula": {
           "formal": "hain",
           "male": "tha",
           "female": "thi",
           "default": "hai",
           "zero_copula_in_present": true
         }
       }
    """
    verbs_cfg = config.get("verbs", {})
    cop_cfg = verbs_cfg.get("copula", {})

    if isinstance(cop_cfg, str):
        return cop_cfg

    if not isinstance(cop_cfg, dict):
        return ""

    if cop_cfg.get("zero_copula_in_present", False):
        return ""

    norm_gender = str(gender or "").strip().lower()
    if norm_gender in {"m", "male", "masc", "masculine"}:
        norm_gender = "male"
    elif norm_gender in {"f", "female", "fem", "feminine"}:
        norm_gender = "female"

    return (
        cop_cfg.get("formal")
        or cop_cfg.get(norm_gender)
        or cop_cfg.get("default")
        or ""
    )


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point for Indo-Aryan Biographies.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female' (case-insensitive; other values passed through).
        prof_lemma (str): Profession (base / citation form).
        nat_lemma (str): Nationality (base / citation form).
        config (dict): The merged configuration card for the specific language.

    Returns:
        str: The fully inflected sentence.
    """
    # 1. Initialize Morphology Engine
    morph = IndoAryanMorphology(config)

    # 2. Normalize gender for safety
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

    # 3. Get Predicate Components
    # Expected return shape:
    #   {
    #     "profession": <inflected profession>,
    #     "nationality": <inflected nationality>,
    #     "copula": <copula or empty string for zero-copula languages>
    #   }
    parts = morph.render_simple_bio_predicates(prof_lemma, nat_lemma, norm_gender)

    nationality = parts.get("nationality", "") or ""
    profession = parts.get("profession", "") or ""
    copula = parts.get("copula", "")

    if copula is None or copula == "":
        copula = _select_copula_from_config(config, norm_gender)

    # 4. Assembly
    #
    # Support both the newer `{copula}` placeholder and the legacy `{is_verb}` one.
    # Default template keeps predicate order natural for many Indo-Aryan cards.
    structure = config.get(
        "structure",
        "{name} {nationality} {profession} {copula}.",
    )

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{is_verb}", copula)  # legacy placeholder
    sentence = sentence.replace("{nationality}", nationality)
    sentence = sentence.replace("{profession}", profession)

    # Cleanup extra whitespace (important for zero-copula languages)
    sentence = " ".join(sentence.split())

    # Ensure final punctuation if the template did not already include it
    punctuation = config.get("syntax", {}).get("punctuation", ".")
    if punctuation and not sentence.endswith(punctuation):
        sentence += punctuation

    return sentence