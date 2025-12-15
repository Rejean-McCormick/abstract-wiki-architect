# morphology\koreanic.py
"""
KOREANIC MORPHOLOGY MODULE
--------------------------
Helpers for Koreanic (KO) morphology and phonology that can be reused
by higher-level engines or construction modules.

This module is intentionally small and data-driven:

- Batchim detection via Unicode Hangul decomposition.
- Particle selection (topic/subject/object) with consonant/vowel variants.
- Copula suffix selection based on speech level and batchim.
"""

from typing import Dict, Any


def has_batchim(word: str) -> bool:
    """
    Return True if the last character of `word` has a final consonant (batchim).

    Uses Unicode Hangul Syllables decomposition:
    - Range: AC00–D7A3
    - (code - 0xAC00) % 28 == 0  -> no batchim (vowel-final)
    - (code - 0xAC00) % 28 > 0   -> batchim present (consonant-final)

    For non-Hangul (e.g. Latin-script names), falls back to a simple
    vowel test and assumes consonant-final otherwise.
    """
    if not word:
        return False

    last_char = word[-1]
    code = ord(last_char)

    # Hangul Syllables block
    if 0xAC00 <= code <= 0xD7A3:
        final_consonant_index = (code - 0xAC00) % 28
        return final_consonant_index > 0

    # Fallback for non-Hangul: naive Latin vowel check
    if last_char.lower() in "aeiou":
        return False
    return True


def _select_variant_by_batchim(
    word: str,
    variants: Dict[str, str],
    consonant_key: str = "consonant",
    vowel_key: str = "vowel",
) -> str:
    """
    Generic helper to choose between consonant/vowel variants
    based on whether `word` has batchim.
    """
    if isinstance(variants, str):
        # Invariant form (no consonant/vowel distinction)
        return variants

    if has_batchim(word):
        return variants.get(consonant_key, "")
    return variants.get(vowel_key, "")


def get_particle(word: str, particle_type: str, config: Dict[str, Any]) -> str:
    """
    Select a case/topic particle for `word` based on batchim.

    Args:
        word: Surface form the particle will attach to.
        particle_type: One of 'topic', 'subject', 'object', etc.
        config: Full language config, expected to contain 'particles'.

    Returns:
        The appropriate particle string (without a preceding space).
    """
    particles = config.get("particles", {})
    rules = particles.get(particle_type, {})

    return _select_variant_by_batchim(
        word,
        rules,
        consonant_key="consonant",
        vowel_key="vowel",
    )


def get_topic_particle(name: str, config: Dict[str, Any]) -> str:
    """
    Convenience wrapper to get the topic particle for a name.
    """
    return get_particle(name, "topic", config)


def get_subject_particle(noun: str, config: Dict[str, Any]) -> str:
    """
    Convenience wrapper to get the subject particle for a noun.
    """
    return get_particle(noun, "subject", config)


def get_object_particle(noun: str, config: Dict[str, Any]) -> str:
    """
    Convenience wrapper to get the object particle for a noun.
    """
    return get_particle(noun, "object", config)


def get_copula_suffix(
    predicate_word: str,
    config: Dict[str, Any],
    level: str | None = None,
) -> str:
    """
    Select the copula suffix to attach to a predicate (e.g., profession).

    Args:
        predicate_word: The word the copula will attach to.
        config: Full language config, expected to contain 'syntax' and 'verbs'.
        level: Optional speech level ('plain', 'polite', 'formal').
               If None, uses syntax.speech_level or defaults to 'plain'.

    Returns:
        The copula form (suffix or invariant string) to append.
    """
    syntax = config.get("syntax", {})
    verbs = config.get("verbs", {})

    if level is None:
        level = syntax.get("speech_level", "plain")

    copula_block = verbs.get("copula", {})
    rules = copula_block.get(level, copula_block.get("default", ""))

    # If rules is a simple string (invariant form like 'imnida' or 'da')
    if isinstance(rules, str):
        return rules

    # Otherwise, expect {"consonant": "...", "vowel": "..."}
    return _select_variant_by_batchim(
        predicate_word,
        rules,
        consonant_key="consonant",
        vowel_key="vowel",
    )


def attach_copula(
    predicate_word: str, config: Dict[str, Any], level: str | None = None
) -> str:
    """
    Convenience helper: return predicate_word + appropriate copula suffix.
    """
    suffix = get_copula_suffix(predicate_word, config, level=level)
    return f"{predicate_word}{suffix}"
