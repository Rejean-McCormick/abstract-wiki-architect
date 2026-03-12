# app/core/domain/constructions/coordination_clauses.py
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
- Takes a list of already realized clause strings.
- Optionally strips sentence-final punctuation from each clause.
- Joins them using language-specific conjunction(s) and comma rules.
- Optionally delegates whitespace normalization and sentence-final
  punctuation to the morphology layer.

It does not build clauses from abstract semantics; that is the job of
other constructions. Here, we are purely combining strings.

Canonical runtime notes
=======================

- Stable construction ID: ``coordination_clauses``
- Canonical slot-map shape:

    {
        "clauses": ["Clause one", "Clause two", ...],   # required
        "conj_type": "and"                              # optional
    }

This keeps plan-level fields out of the slot map and preserves a stable,
backend-agnostic construction boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


__all__ = [
    "MorphologyAPI",
    "CoordinationClausesSlots",
    "CoordinationClausesConstruction",
    "realize_coordination_clauses",
]


_PUNCTUATION_CHARS = ".!?"


class MorphologyAPI(Protocol):
    """
    Optional post-processing protocol used by this construction.

    Concrete morphology/rendering layers may implement either or both hooks.
    """

    def normalize_whitespace(self, text: str) -> str:
        ...

    def finalize_sentence(self, text: str) -> str:
        ...


@dataclass(slots=True)
class CoordinationClausesSlots:
    """
    Canonical slot bundle for ``coordination_clauses``.

    Required:
        clauses:
            Ordered clause surfaces to coordinate.

    Optional:
        conj_type:
            Logical conjunction label, e.g. "and", "or", "but".
    """

    clauses: list[str] = field(default_factory=list)
    conj_type: str = "and"

    @classmethod
    def from_mapping(cls, slots: Mapping[str, Any]) -> "CoordinationClausesSlots":
        if not isinstance(slots, Mapping):
            raise TypeError("slots must be a mapping")

        raw_clauses = slots.get("clauses")
        if raw_clauses is None:
            raise ValueError("coordination_clauses requires slot 'clauses'")

        if not isinstance(raw_clauses, list):
            raise TypeError("slot 'clauses' must be a list of strings")

        clauses = [str(item) for item in raw_clauses if isinstance(item, str)]
        conj_type = str(slots.get("conj_type", "and") or "and").strip() or "and"

        return cls(clauses=clauses, conj_type=conj_type)


def _get_coordination_cfg(lang_profile: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return configuration for coordination of clauses."""
    profile = lang_profile if isinstance(lang_profile, Mapping) else {}
    cfg = profile.get("coordination_clauses", {}) or {}
    if not isinstance(cfg, Mapping):
        cfg = {}

    conjunctions = cfg.get("conjunctions", {}) or {}
    if not isinstance(conjunctions, Mapping):
        conjunctions = {}

    return {
        "default_conjunction": str(cfg.get("default_conjunction", "and") or "and"),
        "conjunctions": {
            str(key): str(value)
            for key, value in conjunctions.items()
            if isinstance(key, str) and isinstance(value, str) and value.strip()
        },
        "serial_comma": bool(cfg.get("serial_comma", True)),
        "strip_final_punctuation": bool(cfg.get("strip_final_punctuation", True)),
    }


def _select_conjunction(cfg: Mapping[str, Any], conj_type: str) -> str:
    """
    Select the surface conjunction string for a given logical type.

    ``conj_type`` is a key like ``and``, ``or``, or ``but``.
    """
    conj_label = str(conj_type or "").strip() or "and"
    conj_map = cfg.get("conjunctions", {}) or {}

    if conj_label in conj_map and isinstance(conj_map[conj_label], str):
        return conj_map[conj_label]

    default_label = str(cfg.get("default_conjunction", "and") or "and")
    if default_label in conj_map and isinstance(conj_map[default_label], str):
        return conj_map[default_label]

    return conj_label


def _strip_trailing_punctuation(text: str) -> str:
    """Strip a single trailing punctuation mark (., !, ?) if present."""
    stripped = text.rstrip()
    if stripped and stripped[-1] in _PUNCTUATION_CHARS:
        return stripped[:-1].rstrip()
    return stripped


def _clean_clauses(clauses: list[str], *, strip_final_punctuation: bool) -> list[str]:
    cleaned = [c.strip() for c in clauses if isinstance(c, str) and c.strip()]
    if not cleaned:
        return []

    if strip_final_punctuation:
        return [_strip_trailing_punctuation(c) for c in cleaned]
    return cleaned


def _join_with_conjunction(
    clauses: list[str],
    conjunction: str,
    serial_comma: bool,
) -> tuple[str, list[str]]:
    """
    Join a list of clauses using a conjunction and optional serial comma.

    Returns:
        (surface_text, token_list)
    """
    n = len(clauses)

    if n == 0:
        return "", []

    if n == 1:
        return clauses[0], [clauses[0]]

    if n == 2:
        tokens = [clauses[0], conjunction, clauses[1]]
        return " ".join(tokens), tokens

    initial = clauses[:-1]
    last = clauses[-1]

    if serial_comma:
        initial_str = ", ".join(initial) + ","
        tokens = [initial_str, conjunction, last]
        return " ".join(tokens), tokens

    initial_str = ", ".join(initial)
    tokens = [initial_str, conjunction, last]
    return " ".join(tokens), tokens


def _finalize_text(text: str, morph_api: Any) -> str:
    if not text:
        return ""

    if hasattr(morph_api, "normalize_whitespace"):
        text = morph_api.normalize_whitespace(text)

    if hasattr(morph_api, "finalize_sentence"):
        return morph_api.finalize_sentence(text)

    text = text.strip()
    if not text:
        return ""
    if text[-1] in _PUNCTUATION_CHARS:
        return text
    return text + "."


class CoordinationClausesConstruction:
    """
    Construction-centered runtime wrapper for clause coordination.

    This class keeps a stable runtime identity and returns a JSON-friendly
    realization bundle suitable for renderer/debug plumbing.
    """

    id = "coordination_clauses"
    required_slots = ("clauses",)
    optional_slots = ("conj_type",)

    def realize(
        self,
        slots: Mapping[str, Any] | CoordinationClausesSlots,
        lang_profile: Mapping[str, Any] | None,
        morph_api: Any,
    ) -> dict[str, Any]:
        if isinstance(slots, CoordinationClausesSlots):
            slot_bundle = slots
        else:
            slot_bundle = CoordinationClausesSlots.from_mapping(slots)

        cfg = _get_coordination_cfg(lang_profile)
        cleaned_clauses = _clean_clauses(
            slot_bundle.clauses,
            strip_final_punctuation=cfg["strip_final_punctuation"],
        )

        if not cleaned_clauses:
            return {
                "construction_id": self.id,
                "text": "",
                "tokens": [],
                "clauses": [],
                "conjunction": "",
                "meta": {
                    "clause_count": 0,
                    "conj_type": slot_bundle.conj_type,
                    "serial_comma": cfg["serial_comma"],
                    "strip_final_punctuation": cfg["strip_final_punctuation"],
                },
            }

        conjunction = _select_conjunction(cfg, slot_bundle.conj_type)
        core_text, tokens = _join_with_conjunction(
            cleaned_clauses,
            conjunction,
            cfg["serial_comma"],
        )
        text = _finalize_text(core_text, morph_api)

        return {
            "construction_id": self.id,
            "text": text,
            "tokens": tokens,
            "clauses": cleaned_clauses,
            "conjunction": conjunction,
            "meta": {
                "clause_count": len(cleaned_clauses),
                "conj_type": slot_bundle.conj_type,
                "serial_comma": cfg["serial_comma"],
                "strip_final_punctuation": cfg["strip_final_punctuation"],
            },
        }


def realize_coordination_clauses(
    clauses: list[str],
    lang_profile: Mapping[str, Any] | None,
    morph_api: Any,
    conj_type: str = "and",
) -> str:
    """
    Backward-compatible functional interface.

    Returns only the final text surface, matching the legacy API that existing
    callers expect.
    """
    result = CoordinationClausesConstruction().realize(
        {"clauses": clauses, "conj_type": conj_type},
        lang_profile,
        morph_api,
    )
    return str(result.get("text", "")) or ""