# app\adapters\engines\engines\polysynthetic.py
# engines\polysynthetic.py
"""
POLYSYNTHETIC LANGUAGE ENGINE
-----------------------------
A data-driven renderer for polysynthetic languages (IU, QU, KL).

This engine supports two config styles:

1. Preferred modern style:
   Uses the shared morphology helper in
   `app.core.domain.morphology.polysynthetic.build_polysynthetic_verb`
   when the language card provides agreement / TAM / incorporation data.

2. Legacy bio style:
   Keeps backward compatibility with older cards that define:
   - morphology.verbalizers.copula
   - morphology.person_markers.3sg
   - morphology.derivation.origin

The output remains template-driven, with `{predicate}` as the main slot.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    # Actual repo path
    from app.core.domain.morphology.polysynthetic import build_polysynthetic_verb
except ImportError:  # pragma: no cover - backward compatibility
    from morphology.polysynthetic import build_polysynthetic_verb


def render_bio(
    name: str,
    gender: str,
    prof_lemma: str,
    nat_lemma: str,
    config: Dict[str, Any],
) -> str:
    """
    Main entry point for polysynthetic biography rendering.

    Args:
        name: Subject name.
        gender: Natural gender label (currently unused by the core logic).
        prof_lemma: Profession root / predicate nominal root.
        nat_lemma: Nationality / origin root.
        config: Language configuration card.

    Returns:
        str: Realized biography sentence.
    """
    name = str(name or "").strip()
    prof_lemma = str(prof_lemma or "").strip()
    nat_lemma = str(nat_lemma or "").strip()

    structure = config.get("structure", "{name} {predicate}.")
    syntax = config.get("syntax", {}) or {}
    morph_rules = config.get("morphology", {}) or {}

    predicate, nat_surface = _build_predicate(
        prof_lemma=prof_lemma,
        nat_lemma=nat_lemma,
        config=config,
    )

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{predicate}", predicate)

    # Compatibility placeholders for templates that still expect split fields.
    sentence = sentence.replace("{profession}", predicate)
    sentence = sentence.replace("{nationality}", nat_surface)
    sentence = sentence.replace("{copula}", "")
    sentence = sentence.replace("{is_verb}", "")

    # Optional topic marker / name particle hook if a config wants it.
    sentence = sentence.replace("{topic_marker}", str(syntax.get("topic_marker", "")))
    sentence = sentence.replace("{name_marker}", str(syntax.get("name_marker", "")))

    return _cleanup_text(sentence)


def _build_predicate(
    *,
    prof_lemma: str,
    nat_lemma: str,
    config: Dict[str, Any],
) -> tuple[str, str]:
    """
    Return `(predicate_surface, nationality_surface)`.

    `nationality_surface` is only non-empty when the chosen strategy keeps it
    as a separate surface word, so legacy templates can still fill
    `{nationality}` if needed.
    """
    syntax = config.get("syntax", {}) or {}
    morph_rules = config.get("morphology", {}) or {}

    nationality_strategy = str(
        morph_rules.get("nationality_strategy", "separate")
    ).strip().lower()
    nationality_position = str(
        morph_rules.get("nationality_position", "before")
    ).strip().lower()

    use_shared_builder = _can_use_shared_builder(config)

    if use_shared_builder:
        predicate_core = _build_with_shared_morphology(
            prof_lemma=prof_lemma,
            nat_lemma=nat_lemma,
            config=config,
            nationality_strategy=nationality_strategy,
        )
    else:
        predicate_core = _build_with_legacy_bio_logic(
            prof_lemma=prof_lemma,
            config=config,
        )

    nat_surface = ""
    if nat_lemma and nationality_strategy not in {"omit", "incorporate"}:
        nat_surface = _derive_origin_legacy(nat_lemma, config)

    if nat_surface:
        if nationality_position == "after":
            predicate = f"{predicate_core} {nat_surface}"
        else:
            predicate = f"{nat_surface} {predicate_core}"
    else:
        predicate = predicate_core

    return _cleanup_text(predicate), _cleanup_text(nat_surface)


def _can_use_shared_builder(config: Dict[str, Any]) -> bool:
    """
    Detect whether the config looks like the newer shared morphology shape.
    """
    return any(
        key in config
        for key in (
            "agreement",
            "tense_suffixes",
            "aspect_suffixes",
            "mood_suffixes",
            "incorporation",
            "derivational",
            "orthography",
        )
    )


def _build_with_shared_morphology(
    *,
    prof_lemma: str,
    nat_lemma: str,
    config: Dict[str, Any],
    nationality_strategy: str,
) -> str:
    """
    Preferred path using the real shared morphology helper.
    """
    syntax = config.get("syntax", {}) or {}
    morph_rules = config.get("morphology", {}) or {}

    subject_features = syntax.get("bio_subject_features", {"person": "3", "number": "sg"})
    object_features = None

    tense = syntax.get("bio_default_tense")
    aspect = syntax.get("bio_default_aspect")
    mood = syntax.get("bio_default_mood")

    derivational_ops = morph_rules.get("bio_derivational_ops", []) or []
    if not isinstance(derivational_ops, list):
        derivational_ops = []

    incorporated_noun: Optional[Dict[str, Any]] = None
    if nat_lemma and nationality_strategy == "incorporate":
        incorporated_noun = {
            "lemma": nat_lemma,
            "role": morph_rules.get("incorporated_nationality_role", "theme"),
            "features": morph_rules.get("incorporated_nationality_features", {}),
        }

    built = build_polysynthetic_verb(
        verb_stem=prof_lemma,
        subject_features=subject_features,
        object_features=object_features,
        tense=tense,
        aspect=aspect,
        mood=mood,
        derivational_ops=derivational_ops,
        incorporated_noun=incorporated_noun,
        full_config=config,
    )

    # If the modern builder returns empty because the card lacks enough detail,
    # fall back to the legacy nominal-predicate path.
    if built:
        return built

    return _build_with_legacy_bio_logic(prof_lemma=prof_lemma, config=config)


def _build_with_legacy_bio_logic(
    *,
    prof_lemma: str,
    config: Dict[str, Any],
) -> str:
    """
    Backward-compatible path for older cards that verbalize a nominal predicate
    via:
      morphology.verbalizers.copula
      morphology.person_markers.3sg
    """
    morph_rules = config.get("morphology", {}) or {}

    predicate = prof_lemma

    copula_suffix = morph_rules.get("verbalizers", {}).get("copula", {})
    predicate = _apply_legacy_suffix(predicate, copula_suffix, config)

    person_suffix = morph_rules.get("person_markers", {}).get("3sg", {})
    predicate = _apply_legacy_suffix(predicate, person_suffix, config)

    return predicate


def _derive_origin_legacy(nat_lemma: str, config: Dict[str, Any]) -> str:
    """
    Legacy nationality/origin derivation:
      morphology.derivation.origin
    """
    if not nat_lemma:
        return ""

    morph_rules = config.get("morphology", {}) or {}
    origin_suffix = morph_rules.get("derivation", {}).get("origin", {})

    if origin_suffix:
        return _apply_legacy_suffix(nat_lemma, origin_suffix, config)

    return nat_lemma


def _apply_legacy_suffix(
    stem: str,
    suffix_data: Any,
    config: Dict[str, Any],
) -> str:
    """
    Apply the old config-driven suffix logic used by the existing engine.

    Supported suffix shapes:
    - "juq"
    - {"default": "juq"}
    - {"variants": {"default": "juq", "vowel": "juq", "k": "tuq", "q": "ruq"},
       "deletion": ["k", "q"]}
    """
    stem = str(stem or "").strip()
    if not stem or not suffix_data:
        return stem

    phonetics = config.get("phonetics", {}) or {}

    if isinstance(suffix_data, str):
        variants = {"default": suffix_data}
        deletion_rules: list[str] = []
    elif isinstance(suffix_data, dict):
        variants = suffix_data.get("variants", {})
        if not variants:
            direct_default = suffix_data.get("default")
            variants = {"default": direct_default} if isinstance(direct_default, str) else {}
        deletion_rules = list(suffix_data.get("deletion", []) or [])
    else:
        return stem

    if not variants:
        return stem

    last_char = stem[-1].lower()
    char_type = phonetics.get("char_types", {}).get(last_char, "default")

    suffix = (
        variants.get(char_type)
        or variants.get(last_char)
        or variants.get("default", "")
    )

    if last_char in deletion_rules or char_type in deletion_rules:
        stem = stem[:-1]

    return f"{stem}{suffix}"


def _cleanup_text(text: str) -> str:
    """
    Collapse repeated spaces and remove spaces before common punctuation.
    """
    text = " ".join(str(text or "").split())
    text = text.replace(" .", ".")
    text = text.replace(" ,", ",")
    text = text.replace(" ;", ";")
    text = text.replace(" :", ":")
    return text.strip()


__all__ = ["render_bio"]