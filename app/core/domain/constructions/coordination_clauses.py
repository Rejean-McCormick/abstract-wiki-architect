# constructions\coordination_clauses.py
"""
COORDINATION_CLAUSES CONSTRUCTION
---------------------------------

Family-agnostic construction for coordinating clauses, e.g.:

    "She discovered polonium and she pioneered research on radioactivity."
    "Elle a découvert le polonium et elle a été une pionnière de la recherche sur la radioactivité."
    "彼女はポロニウムを発見し、放射能研究を先駆けた。"

Abstract pattern (for N >= 2):

    CLAUSE_1 , CLAUSE_2 , ... , CLAUSE_{N-1} [serial comma] CONJ CLAUSE_N

This module:
- Takes a list of *already realized* clause strings.
- Optionally strips sentence-final punctuation from each clause.
- Joins them using language-specific conjunction(s) and comma rules.
- Optionally delegates whitespace normalization and sentence-final
  punctuation to the morphology layer.

It does *not* build clauses from abstract semantics; that is the job of
other constructions. Here, we are purely combining strings.

Expected external interfaces
============================

1) `lang_profile` (dict-like):

    lang_profile["coordination_clauses"] = {
        "default_conjunction": "and",       # fallback conjunction label
        "conjunctions": {
            "and": "and",
            "or": "or",
            "but": "but"
        },
        "serial_comma": True,               # Oxford comma for N >= 3
        "strip_final_punctuation": True     # remove final . ! ? from input clauses
    }

All keys are optional; reasonable defaults are provided.

2) `morph_api` (object):

Optionally implements:

    morph_api.normalize_whitespace(text: str) -> str
    morph_api.finalize_sentence(text: str) -> str

If `finalize_sentence` is not present, this module will add a trailing
period "." if the final string does not already end in punctuation.

3) `clauses` (list of strings):

A non-empty list of surface clause strings. For best results, callers
should pass raw clauses without final punctuation, or enable the
`strip_final_punctuation` option so that this module can safely control
the final sentence punctuation.
"""

from __future__ import annotations

from typing import Any, Dict, List


_PUNCTUATION_CHARS = ".!?"


def _get_coordination_cfg(lang_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return configuration for coordination of clauses."""
    cfg = lang_profile.get("coordination_clauses", {}) or {}
    if not isinstance(cfg, dict):
        cfg = {}

    conjunctions = cfg.get("conjunctions", {}) or {}
    if not isinstance(conjunctions, dict):
        conjunctions = {}

    return {
        "default_conjunction": cfg.get("default_conjunction", "and"),
        "conjunctions": conjunctions,
        "serial_comma": bool(cfg.get("serial_comma", True)),
        "strip_final_punctuation": bool(cfg.get("strip_final_punctuation", True)),
    }


def _select_conjunction(cfg: Dict[str, Any], conj_type: str) -> str:
    """
    Select the surface conjunction string for a given logical type.

    conj_type: a key like "and", "or", "but".
    """
    conj_map = cfg["conjunctions"]
    if conj_type in conj_map and isinstance(conj_map[conj_type], str):
        return conj_map[conj_type]
    # Fallback to default_conjunction
    default_label = cfg["default_conjunction"]
    if default_label in conj_map and isinstance(conj_map[default_label], str):
        return conj_map[default_label]
    # Final fallback: use the label itself
    return conj_type


def _strip_trailing_punctuation(text: str) -> str:
    """Strip a single trailing punctuation mark (., !, ?) if present."""
    if not text:
        return text
    stripped = text.rstrip()
    if stripped and stripped[-1] in _PUNCTUATION_CHARS:
        return stripped[:-1].rstrip()
    return stripped


def _join_with_conjunction(
    clauses: List[str],
    conjunction: str,
    serial_comma: bool,
) -> str:
    """
    Join a list of clauses using a conjunction and optional serial comma.

    For N=1: returns the single clause.
    For N=2: "A CONJ B"
    For N>=3:
        if serial_comma: "A, B, C, CONJ D"
        else:            "A, B, C CONJ D"
    """
    n = len(clauses)
    if n == 0:
        return ""
    if n == 1:
        return clauses[0]

    if n == 2:
        return " ".join([clauses[0], conjunction, clauses[1]])

    # N >= 3
    *initial, last = clauses
    if serial_comma:
        # comma before final conjunction (Oxford comma)
        initial_str = ", ".join(initial)
        return " ".join([initial_str + ",", conjunction, last])
    else:
        # no comma before final conjunction
        initial_str = ", ".join(initial[:-1] + [initial[-1]])
        return " ".join([initial_str, conjunction, last])


def realize_coordination_clauses(
    clauses: List[str],
    lang_profile: Dict[str, Any],
    morph_api: Any,
    conj_type: str = "and",
) -> str:
    """
    Realize a coordinated clause string from a list of clause strings.

    Args:
        clauses:
            List of already-realized clause strings (surface forms).
        lang_profile:
            Language profile config containing a "coordination_clauses"
            section (see module docstring).
        morph_api:
            Morphology / post-processing API. May provide:
                - normalize_whitespace(text: str) -> str
                - finalize_sentence(text: str) -> str
        conj_type:
            Logical conjunction type label (e.g. "and", "or", "but").
            Mapped to a surface form using lang_profile.

    Returns:
        A single coordinated sentence string.
    """
    if not isinstance(clauses, list):
        raise TypeError("clauses must be a list of strings")

    # Filter out empty / whitespace-only clauses
    cleaned_clauses = [c.strip() for c in clauses if isinstance(c, str) and c.strip()]
    if not cleaned_clauses:
        return ""

    cfg = _get_coordination_cfg(lang_profile)

    # Optionally strip final punctuation from each clause
    if cfg["strip_final_punctuation"]:
        stripped = [_strip_trailing_punctuation(c) for c in cleaned_clauses]
    else:
        stripped = cleaned_clauses

    conj_surface = _select_conjunction(cfg, conj_type)
    core = _join_with_conjunction(stripped, conj_surface, cfg["serial_comma"])

    # Optional whitespace normalization
    if hasattr(morph_api, "normalize_whitespace"):
        core = morph_api.normalize_whitespace(core)

    # Delegate final punctuation if available
    if hasattr(morph_api, "finalize_sentence"):
        return morph_api.finalize_sentence(core)

    # Fallback: add a period if no final punctuation
    text = core.strip()
    if not text:
        return text
    if text[-1] in _PUNCTUATION_CHARS:
        return text
    return text + "."
