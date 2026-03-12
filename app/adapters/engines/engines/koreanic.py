# app\adapters\engines\engines\koreanic.py
# engines\koreanic.py
"""
KOREANIC LANGUAGE ENGINE
------------------------
A data-driven renderer for Koreanic languages (KO).

This module orchestrates sentence generation by:
1. Delegating batchim-sensitive particle/copula selection to
   `morphology.koreanic`.
2. Handling sentence structure and assembly.
3. Preserving the legacy `render_bio(...)` engine surface used by the
   family adapter/runtime.

Notes
-----
- `gender` is accepted for compatibility with the shared family-engine API,
  but Korean biography rendering here does not grammatically depend on it.
- Topic particles and copulas attach directly to the preceding token.
- We support both newer `{predicate}` templates and older split-slot templates.
"""

from __future__ import annotations

from typing import Any, Dict

from morphology.koreanic import attach_copula, get_copula_suffix, get_topic_particle


def render_bio(
    name: str,
    gender: str,
    prof_lemma: str,
    nat_lemma: str,
    config: Dict[str, Any],
) -> str:
    """
    Main entry point for Koreanic biography rendering.

    Args:
        name:
            The subject's name.
        gender:
            Compatibility-only input. Usually ignored for grammar here.
        prof_lemma:
            Profession noun.
        nat_lemma:
            Nationality noun/modifier.
        config:
            Per-language configuration card.

    Returns:
        Fully assembled sentence.
    """
    del gender  # accepted for shared-engine compatibility

    # 1. Normalize inputs
    name = str(name or "").strip()
    prof = str(prof_lemma or "").strip()
    nat = str(nat_lemma or "").strip()
    config = config or {}

    syntax = config.get("syntax", {})

    # Current/legacy default remains compatible with the existing file:
    #   "{name}{topic} {nationality} {profession}{copula}."
    #
    # We also support newer templates that use:
    #   "{name}{topic} {predicate}."
    structure = config.get(
        "structure",
        "{name}{topic} {nationality} {profession}{copula}.",
    )

    # 2. Delegate phonology / morphology
    topic_marker = get_topic_particle(name, config)
    copula_suffix = get_copula_suffix(prof, config)
    predicative_profession = attach_copula(prof, config)

    # Combined predicate for templates that prefer one slot.
    predicate = " ".join(
        part for part in (nat, predicative_profession) if part
    ).strip()

    # 3. Assembly
    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{topic}", topic_marker)
    sentence = sentence.replace("{topic_particle}", topic_marker)

    sentence = sentence.replace("{predicate}", predicate)

    sentence = sentence.replace("{nationality}", nat)
    sentence = sentence.replace("{profession}", prof)
    sentence = sentence.replace("{profession_with_copula}", predicative_profession)

    # In Korean the copula is normally suffixed to the predicate noun.
    # We still expose split placeholders for backward compatibility.
    sentence = sentence.replace("{copula}", copula_suffix)
    sentence = sentence.replace("{copula_suffix}", copula_suffix)
    sentence = sentence.replace("{is_verb}", copula_suffix)

    # Article has no grammatical role here, but some shared templates may include it.
    sentence = sentence.replace("{article}", "")

    # 4. Cleanup
    # Korean keeps normal word spacing, but particles/copu la remain attached.
    sentence = " ".join(sentence.split())

    punctuation = syntax.get("punctuation", ".")
    if sentence and sentence[-1] not in ".!?。":
        sentence += punctuation

    return sentence