# semantics\relational\temporal_relation_frame.py
# semantics/relational/temporal_relation_frame.py
# -----------------------------------------------
#
# TemporalRelationFrame
# =====================
#
# High-level semantic frame for temporal relations such as:
#
#   - "X happened before Y."
#   - "X has been ongoing since Y."
#   - "X takes place every July."
#
# This corresponds to the `TemporalRelationFrame` described in
# `docs/FRAMES_RELATIONAL.md`. It is intended to be used as a
# *relational* building block inside larger frames (event narratives,
# timelines, biographies, etc.), rather than as a top-level routed
# frame with its own NLG engine.
#
# The concrete lexical / syntactic realization (choice of connectives,
# adverbials, clause ordering, etc.) is handled by higher layers.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from semantics.types import TimeSpan


@dataclass
class TemporalRelationFrame:
    """
    Temporal relationship between events or states.

    Examples
    --------
    - "The war ended before the treaty was signed."
    - "The project has been ongoing since 2010."
    - "The festival takes place every July."

    Semantics
    ---------
    This frame encodes a high-level temporal relation between two
    arguments (`left` and `right`), which can be:

        * full `Event` objects,
        * `Entity` objects standing in for events or states
          (e.g. "the war", "the treaty"), or
        * explicit `TimeSpan` objects.

    The optional `left_time` / `right_time` fields allow callers to
    attach explicit time spans even when `left` / `right` are entities
    or events without their own `time` field populated.

    `recurrence` can be used for seasonal/periodic situations (e.g.
    "annual", "monthly") to support sentences like:

        * "The festival takes place every July."
    """

    # Core relation
    left: Any
    """Left argument of the relation (event, entity, or TimeSpan)."""

    right: Any
    """Right argument of the relation (event, entity, or TimeSpan)."""

    relation: str
    """
    Temporal relation label.

    Expected values (non-exhaustive, project-specific):

        - "before"
        - "after"
        - "since"
        - "until"
        - "during"
        - "throughout"
        - "around"
        - "by"   (as in "by 1990")
    """

    # Optional identifier for tracing / debugging
    id: Optional[str] = None

    # Optional explicit spans when they are not implicit in left/right
    left_time: Optional[TimeSpan] = None
    right_time: Optional[TimeSpan] = None

    # Recurrence for seasonal / periodic events ("annual", "monthly", ...)
    recurrence: Optional[str] = None

    # Provenance / meta
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["TemporalRelationFrame"]
