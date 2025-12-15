# semantics\relational\part_whole_composition_frame.py
"""
semantics/relational/part_whole_composition_frame.py
----------------------------------------------------

Semantic frame for part–whole and composition relations.

This frame captures relationships where one entity (the *whole*) is
composed of, subdivided into, or otherwise structurally related to one
or more *parts*. It is intended for encyclopedic sentences such as:

    - "France is divided into 18 administrative regions."
    - "The solar system consists of the Sun and the objects that orbit it."
    - "The human heart has four chambers: two atria and two ventricles."

Design goals
============

- Language-neutral:
    All labels (e.g. "region", "member state") are stored as lemma-like
    keys, not as surface strings.

- Simple but flexible:
    The core structure is `whole` + `parts`, with optional lemma fields
    describing the roles ("country" / "region") and the relation
    ("consists of", "is divided into", etc.).

- Compatible with the generic Frame protocol:
    The `frame_type` attribute is provided as a read-only property so
    that this type can be treated as a `Frame` without affecting
    dataclass field ordering.

Typical usage
=============

    from semantics.types import Entity
    from semantics.relational.part_whole_composition_frame import (
        PartWholeCompositionFrame,
    )

    france = Entity(id="Q142", name="France")
    region = Entity(id="Q36784", name="Occitanie")

    frame = PartWholeCompositionFrame(
        whole=france,
        parts=[region],
        whole_role_lemmas=["country"],
        part_role_lemmas=["region"],
        relation_lemmas=["administrative subdivision"],
    )

Downstream NLG code can then choose patterns like:

    - "{whole} is a {whole_role} in {higher_place}. It is divided into
       {N} {part_role_plural}."
    - "{parts} are {part_role_plural} of {whole}."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from semantics.types import Entity


__all__ = ["PartWholeCompositionFrame"]


@dataclass
class PartWholeCompositionFrame:
    """
    Part–whole / composition semantic frame.

    Core structure
    --------------

    whole:
        The entity that is being described as a whole or container.

        Examples:
            - A country that is divided into regions
            - A city composed of districts
            - An organization composed of departments
            - A physical object composed of components

    parts:
        List of entities that are parts / components / subdivisions of
        `whole`. Each item is an `Entity` and may itself carry additional
        metadata (e.g. IDs, extra attributes).

    Role and relation labels
    ------------------------

    whole_role_lemmas:
        Lemmas describing the semantic *role* or type of the whole, such
        as "country", "university", "organ", "solar system". These are
        intended to drive constructions like "X is a Y".

    part_role_lemmas:
        Lemmas describing the semantic *role* or type of the parts, such
        as "region", "department", "chamber", "member state".

    relation_lemmas:
        Lemmas describing the type of part–whole relation, for example:

            ["subdivision"]
            ["component"]
            ["member"]
            ["administrative subdivision"]

        These may correspond to patterns like "is divided into", "consists
        of", "is composed of", etc. The mapping to actual surface forms is
        handled downstream.

    Additional metadata
    -------------------

    attributes:
        Generic attribute map for structured, JSON-like data that is
        specific to this part–whole relation rather than to the entities
        themselves. For example:

            {
                "part_count": 18,
                "ordering": "geographical",
                "is_exhaustive": True
            }

        You are free to define project-specific keys; NLG code may look
        for a small set of known keys (e.g. "part_count") but must
        tolerate arbitrary ones.

    extra:
        Opaque metadata bag for bookkeeping and provenance (e.g. original
        JSON rows, Wikidata statement IDs). It is not interpreted by
        language-independent NLG logic.

    Notes
    -----

    - This frame is neutral about directionality: engines may choose to
      realize it as "whole → parts" ("X is divided into A, B, C") or
      "parts → whole" ("A, B, and C are regions of X") depending on the
      discourse context.

    - If you need multiple distinct part–whole relations for the same
      pair of entities (e.g. both "administrative region" and "historical
      province"), it is often clearer to create separate frames, each
      with its own `relation_lemmas` and role lemmas.
    """

    # Core entities
    whole: Entity
    parts: List[Entity] = field(default_factory=list)

    # Role and relation description
    whole_role_lemmas: List[str] = field(default_factory=list)
    part_role_lemmas: List[str] = field(default_factory=list)
    relation_lemmas: List[str] = field(default_factory=list)

    # Generic extension points
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Frame protocol support
    # ------------------------------------------------------------------

    @property
    def frame_type(self) -> str:
        """
        Stable label used for routing / engine selection.

        For this frame we use a dotted name to indicate both the
        relational nature and the specific subtype.
        """
        return "rel.part_whole_composition"
