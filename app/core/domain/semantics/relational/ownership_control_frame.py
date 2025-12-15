# semantics\relational\ownership_control_frame.py
"""
semantics/relational/ownership_control_frame.py
----------------------------------------------

Semantic frame for ownership and control relations.

This module defines a small, typed data class that captures facts such as:

    - "X owns Y."
    - "X controls Y."
    - "X operates Y."
    - "X holds a 51% stake in Y."

The frame is designed to be:

    - language-independent (no morphology or word order here),
    - simple enough for direct use by higher-level NLG components,
    - flexible enough to handle a range of ownership / control scenarios.

Typical uses include:

    - corporate ownership trees (parent company, subsidiaries)
    - state ownership or control of enterprises
    - operation and management relationships (e.g. "X operates Y airport")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Optional

from semantics.types import Entity, TimeSpan


@dataclass
class OwnershipControlFrame:
    """
    Ownership / control relation between two entities.

    Core participants
    -----------------

    owner:
        The owning or controlling entity. This can be a person,
        organization, state, or any other entity capable of holding
        ownership or control, represented as an :class:`Entity`.

    asset:
        The entity that is owned, controlled, operated, or managed by
        ``owner``. This might be, for example, a company, a facility,
        a financial instrument, or a brand.

    relation_type:
        Coarse label describing the nature of the relation, typically
        one of (but not limited to):

            - "ownership"
            - "majority_ownership"
            - "minority_ownership"
            - "control"
            - "operation"
            - "management"

        The NLG layer may use this to choose between "owns",
        "controls", "operates", etc.

    Quantitative and qualitative extent
    -----------------------------------

    ownership_share_pct:
        Optional approximate percentage (0–100) of ownership stake.
        For example, 51.0 for a 51% majority stake. If omitted, the
        relation may still be described qualitatively.

    control_level:
        Optional qualitative description of the level of control, such
        as:

            - "full"
            - "majority"
            - "minority"
            - "operational_only"

        This is particularly useful when ``ownership_share_pct`` is
        unknown or not the primary signal.

    Temporal and jurisdictional context
    -----------------------------------

    time_span:
        Optional :class:`TimeSpan` indicating when the ownership /
        control relation holds. For example, the period during which a
        company owns a subsidiary.

    jurisdiction:
        Optional entity representing the jurisdiction or regulatory
        context in which the ownership / control relation is relevant.
        This is typically a country or region entity, but is not
        restricted.

    Extensibility
    -------------

    attributes:
        Open-ended JSON-like attribute map for structured additional
        facts, for example:

            {
                "voting_rights_pct": 60.0,
                "economic_interest_pct": 40.0,
                "is_listed_parent": true
            }

        The exact keys are project-specific and may or may not be
        verbalized.

    extra:
        Bag for opaque metadata that is not intended to directly affect
        surface realization (e.g. source IDs, original JSON records).

    frame_type:
        Stable label for routing / planning. For this frame we use
        "relation.ownership". It is not part of the constructor
        signature; it is fixed for all instances of this class.
    """

    # Routing label (fixed)
    # Updated to match test expectation "relation.ownership"
    frame_type: ClassVar[str] = "relation.ownership"

    # Core participants (required)
    owner: Entity
    asset: Entity

    # Nature of the relation
    relation_type: str = "ownership"

    # Quantitative and qualitative extent
    ownership_share_pct: Optional[float] = None
    control_level: Optional[str] = None

    # Temporal / jurisdictional context
    time_span: Optional[TimeSpan] = None
    jurisdiction: Optional[Entity] = None

    # Extensibility
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["OwnershipControlFrame"]
