# semantics\relational\comparative_ranking_frame.py
"""
semantics/relational/comparative_ranking_frame.py
=================================================

Comparative / superlative and ranking facts over a property.

This module defines a light-weight semantic frame for statements such as:

    - "X is larger than Y."
    - "X is the largest city in Z."
    - "X is the second-oldest university in the country."

The frame is property-centric and entity-centric at the same time: it
captures which subject is being compared, which property is used for the
comparison (population, area, age, etc.), what the comparison type is,
and—optionally—any explicit numeric data that backs it.

Lexicalization (adjectives, superlatives, prepositions) is handled by
constructions; this module only defines the abstract data shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from semantics.types import Entity, TimeSpan
from semantics.common.quantity import Quantity


@dataclass
class ComparativeFrame:
    """
    Comparative / superlative / ranking statement over a single property.

    Examples
    --------
        - "X is larger than Y."
        - "X is the largest city in Z."
        - "X is the second-oldest university in the country."

    Semantics
    ---------
    * ``subject`` is the entity being described (X).
    * ``property`` is the property along which comparison is made,
      such as "population", "area", "age", "height".
    * ``comparison_type`` specifies the logical shape:

          - "comparative"  → X vs Y ("larger than Y")
          - "superlative"  → X is best/worst within some domain
          - "ranking"      → X has a specific rank within some domain

    * ``standard`` is the comparison standard (Y) in "larger than Y".
    * ``direction`` tells whether X is greater or less than the standard.
    * ``rank`` and ``domain`` are used for superlatives / rankings.

    Optional numeric backing can be provided via ``subject_quantity`` and
    ``standard_quantity``; these are not required for realization, but
    allow engines to use approximate phrasing ("about 3.5 million") or
    to surface explicit numbers where appropriate.
    """

    # Optional stable identifier for this fact
    id: Optional[str] = None

    # Core comparative statement
    subject: Optional[Entity] = None  # X
    property: Optional[str] = None  # "population", "area", "age", …
    comparison_type: Optional[str] = None  # "comparative" | "superlative" | "ranking"

    # Comparative:
    standard: Optional[Entity] = None  # Y in "larger than Y"
    direction: str = "greater"  # "greater" | "less"

    # Superlative / ranking:
    rank: Optional[int] = None  # 1, 2, 3, …
    domain: Optional[Entity] = None  # set/domain: country, region, league
    domain_scope: Optional[str] = None  # "in", "among", "within" (prepositional flavor)

    # Optional explicit numeric data, if available
    subject_quantity: Optional[Quantity] = None
    standard_quantity: Optional[Quantity] = None

    # Temporal anchoring and metadata
    time: Optional[TimeSpan] = None
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ComparativeFrame"]
