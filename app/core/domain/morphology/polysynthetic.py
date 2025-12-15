# morphology\polysynthetic.py
"""
POLYSYNTHETIC MORPHOLOGY LAYER
------------------------------

Shared morphology helpers for polysynthetic languages.

This module is deliberately very abstract and data-driven. It does NOT try to
encode the rules of any particular language. Instead, it provides a small,
configurable pipeline to build complex verb words with:

* Agreement prefixes (subject / object / other core arguments)
* Optional incorporated noun stems
* Optional derivational morphemes (causative, applicative, etc.)
* Tense / aspect / mood suffixes
* Light orthographic cleanup

A typical per-language config could look like:

{
  "agreement": {
    "subject_prefixes": {
      "1sg": "ni-",
      "2sg": "ci-",
      "3sg": "i-",
      "1pl": "ni-",
      "2pl": "ci-",
      "3pl": "i-"
    },
    "object_prefixes": {
      "1sg": "wɛ-ni-",
      "2sg": "wɛ-ci-",
      "3sg": "wa-"
    },
    "fallback_prefix": ""
  },

  "tense_suffixes": {
    "past": "-wá",
    "present": "",
    "future": "-k"
  },

  "aspect_suffixes": {
    "imperfective": "-ta",
    "perfective": ""
  },

  "mood_suffixes": {
    "indicative": "",
    "subjunctive": "-ke"
  },

  "derivational": {
    "causative": "-ti-",
    "applicative": "-mu-",
    "reciprocal": "-šɨ-"
  },

  "incorporation": {
    "allowed_roles": ["patient", "theme"],
    "noun_class_prefixes": {
      "generic": "",
      "animate": "at-",
      "inanimate": "am-"
    }
  },

  "orthography": {
    "merge_double_vowels": true,
    "merge_double_consonants": false,
    "hyphen_between_prefixes": false
  }
}

Downstream code is expected to:

1) Decide which arguments (subject, object, etc.) are present,
2) Optionally choose one noun to incorporate,
3) Call `build_polysynthetic_verb(...)` with the abstract feature bundle.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

Person = Literal["1", "2", "3"]
Number = Literal["sg", "pl"]


def _person_number_key(person: str, number: str) -> str:
    """
    Normalize a (person, number) pair into a simple key like '1sg', '3pl', etc.
    """
    p = person.strip()
    n = number.strip().lower()
    if n not in {"sg", "pl"}:
        # Default to sg if something odd is passed.
        n = "sg"
    return f"{p}{n}"


def _select_agreement_prefix(
    role: str,
    features: Dict[str, Any],
    agreement_cfg: Dict[str, Any],
) -> str:
    """
    Select an agreement prefix for a given grammatical role.

    Args:
        role:
            'subject' or 'object' (or any other key that the config supports,
            like 'beneficiary', if present).
        features:
            Dictionary with at least 'person' and 'number', e.g.:
                { "person": "1", "number": "sg" }
        agreement_cfg:
            The 'agreement' section from the language config.

    Returns:
        A prefix string or empty string.
    """
    person = str(features.get("person", "3"))
    number = str(features.get("number", "sg"))
    key = _person_number_key(person, number)

    container_name = f"{role}_prefixes"
    container = agreement_cfg.get(container_name, {}) or {}
    if key in container:
        return container[key]

    # If we have full 'agreement_prefixes' (no role), allow a fallback there:
    general = agreement_cfg.get("agreement_prefixes", {}) or {}
    if key in general:
        return general[key]

    return agreement_cfg.get("fallback_prefix", "")


def _select_derivational_sequence(
    operations: List[str],
    derivational_cfg: Dict[str, Any],
) -> List[str]:
    """
    Map a list of abstract derivational operations (e.g. ["causative", "applicative"])
    into a sequence of concrete morphemes.

    Unknown operations are silently ignored.
    """
    morphemes: List[str] = []
    for op in operations:
        morpheme = derivational_cfg.get(op)
        if isinstance(morpheme, str) and morpheme:
            morphemes.append(morpheme)
    return morphemes


def _incorporate_noun(
    noun_lemma: str,
    noun_role: str,
    noun_features: Dict[str, Any],
    incorporation_cfg: Dict[str, Any],
) -> str:
    """
    Build an incorporated noun segment, if allowed.

    Args:
        noun_lemma:
            Base noun stem to incorporate (e.g. 'fish', 'house').
        noun_role:
            Semantic role of the noun in the verb frame (patient, theme, etc.).
        noun_features:
            Additional features (e.g. noun class, animacy). Optional.
        incorporation_cfg:
            The 'incorporation' section from the config.

    Returns:
        The incorporated noun string (possibly empty if incorporation not allowed).
    """
    allowed_roles = set(incorporation_cfg.get("allowed_roles", []) or [])
    if allowed_roles and noun_role not in allowed_roles:
        return ""

    lemma = (noun_lemma or "").strip()
    if not lemma:
        return ""

    noun_class = noun_features.get("noun_class", "generic")
    class_prefixes = incorporation_cfg.get("noun_class_prefixes", {}) or {}
    prefix = class_prefixes.get(noun_class, class_prefixes.get("generic", ""))

    if prefix:
        return prefix + lemma
    return lemma


def _select_tam_suffixes(
    tense: Optional[str],
    aspect: Optional[str],
    mood: Optional[str],
    config: Dict[str, Any],
) -> List[str]:
    """
    Select Tense / Aspect / Mood suffixes in a fixed order.

    Each of tense/aspect/mood may be None; we then either skip it or use the
    'default' key if present.
    """
    suffixes: List[str] = []

    tense_cfg = config.get("tense_suffixes", {}) or {}
    aspect_cfg = config.get("aspect_suffixes", {}) or {}
    mood_cfg = config.get("mood_suffixes", {}) or {}

    if tense is not None:
        s = tense_cfg.get(tense)
        if isinstance(s, str):
            suffixes.append(s)
    elif "default" in tense_cfg:
        s = tense_cfg["default"]
        if isinstance(s, str):
            suffixes.append(s)

    if aspect is not None:
        s = aspect_cfg.get(aspect)
        if isinstance(s, str):
            suffixes.append(s)
    elif "default" in aspect_cfg:
        s = aspect_cfg["default"]
        if isinstance(s, str):
            suffixes.append(s)

    if mood is not None:
        s = mood_cfg.get(mood)
        if isinstance(s, str):
            suffixes.append(s)
    elif "default" in mood_cfg:
        s = mood_cfg["default"]
        if isinstance(s, str):
            suffixes.append(s)

    return suffixes


def _orthographic_cleanup(word: str, orth_cfg: Dict[str, Any]) -> str:
    """
    Apply simple post-hoc orthographic cleanups.

    Intended to handle obviously mechanical things, not detailed
    phonological rules.
    """
    if not word:
        return word

    merge_double_vowels = bool(orth_cfg.get("merge_double_vowels", False))
    merge_double_consonants = bool(orth_cfg.get("merge_double_consonants", False))

    chars: List[str] = []
    for ch in word:
        if chars:
            prev = chars[-1]
            if (
                merge_double_vowels
                and prev == ch
                and prev.lower() in "aeiouàèìòùáéíóúâêîôû"
            ):
                # Skip this vowel (simple collapsing of VV → V)
                continue
            if (
                merge_double_consonants
                and prev == ch
                and prev.isalpha()
                and prev.lower() not in "aeiou"
            ):
                # Skip this consonant (simple CC → C)
                continue
        chars.append(ch)

    return "".join(chars)


def build_polysynthetic_verb(
    verb_stem: str,
    subject_features: Optional[Dict[str, Any]],
    object_features: Optional[Dict[str, Any]],
    tense: Optional[str],
    aspect: Optional[str],
    mood: Optional[str],
    derivational_ops: Optional[List[str]],
    incorporated_noun: Optional[Dict[str, Any]],
    full_config: Dict[str, Any],
) -> str:
    """
    High-level helper to build a polysynthetic verb form.

    Args:
        verb_stem:
            Base verb stem (no agreement / TAM / derivation).
        subject_features:
            e.g. { "person": "1", "number": "sg" } or None.
        object_features:
            e.g. { "person": "3", "number": "sg" } or None.
        tense:
            Abstract tense key (e.g. 'past', 'present', 'future') or None.
        aspect:
            Abstract aspect key (e.g. 'imperfective', 'perfective') or None.
        mood:
            Abstract mood key (e.g. 'indicative', 'subjunctive') or None.
        derivational_ops:
            List of derivational operations (e.g. ["causative", "applicative"]).
        incorporated_noun:
            Either None, or a dict like:
                {
                  "lemma": "fish",
                  "role": "patient",
                  "features": { "noun_class": "animate" }
                }
        full_config:
            Per-language config containing at least:
                "agreement", "tense_suffixes"/"aspect_suffixes"/"mood_suffixes",
                "derivational", "incorporation", "orthography"

    Returns:
        The assembled verb word as a string.
    """
    agreement_cfg = full_config.get("agreement", {}) or {}
    derivational_cfg = full_config.get("derivational", {}) or {}
    incorporation_cfg = full_config.get("incorporation", {}) or {}
    orth_cfg = full_config.get("orthography", {}) or {}

    stem = (verb_stem or "").strip()
    if not stem:
        return ""

    prefixes: List[str] = []
    core_stem = stem
    derivation_slots: List[str] = []
    suffixes: List[str] = []

    # 1. Agreement prefixes (subject, object, etc.)
    if subject_features:
        subj_prefix = _select_agreement_prefix(
            "subject", subject_features, agreement_cfg
        )
        if subj_prefix:
            prefixes.append(subj_prefix)

    if object_features:
        obj_prefix = _select_agreement_prefix("object", object_features, agreement_cfg)
        if obj_prefix:
            prefixes.append(obj_prefix)

    # 2. Incorporated noun, if any.
    if incorporated_noun:
        noun_lemma = incorporated_noun.get("lemma", "")
        noun_role = incorporated_noun.get("role", "patient")
        noun_feats = incorporated_noun.get("features", {}) or {}
        inc_segment = _incorporate_noun(
            noun_lemma,
            noun_role,
            noun_feats,
            incorporation_cfg,
        )
        if inc_segment:
            core_stem = inc_segment + core_stem

    # 3. Derivational morphemes between stem and TAM suffixes.
    if derivational_ops:
        derivation_slots = _select_derivational_sequence(
            derivational_ops,
            derivational_cfg,
        )

    # 4. TAM suffixes.
    suffixes = _select_tam_suffixes(tense, aspect, mood, full_config)

    # 5. Assemble raw string.
    # The exact ordering of prefixes (subject vs object) is language-specific.
    # Here we simply concatenate them in the order we collected them; if a
    # language needs a different order, it can encode this by how it calls
    # the function or by extra config fields.
    hyphen_between_prefixes = bool(orth_cfg.get("hyphen_between_prefixes", False))

    if prefixes:
        if hyphen_between_prefixes:
            prefix_block = "-".join(p for p in prefixes if p)
        else:
            prefix_block = "".join(prefixes)
    else:
        prefix_block = ""

    # Derivational affixes are inserted between the (possibly incorporated)
    # stem and the TAM suffixes.
    deriv_block = "".join(derivation_slots)
    tam_block = "".join(suffixes)

    raw = prefix_block + core_stem + deriv_block + tam_block

    # 6. Orthographic cleanup.
    final = _orthographic_cleanup(raw, orth_cfg)
    return final
