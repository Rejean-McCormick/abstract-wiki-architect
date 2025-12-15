# semantics\relational\membership_affiliation_frame.py
"""
semantics/relational/membership_affiliation_frame.py

Membership / affiliation relational frame.

This module defines the `MembershipFrame` dataclass, which models simple
group-membership or affiliation facts such as:

    - "She is a member of the Academy."
    - "He plays for FC Barcelona."
    - "She belongs to the Green Party."

The schema follows the design in `docs/FRAMES_RELATIONAL.md` (section
"Membership / affiliation (MembershipFrame)").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from semantics.types import Entity, TimeSpan

__all__ = ["MembershipFrame"]


@dataclass
class MembershipFrame:
    """
    Group membership or affiliation.

    Examples:
        - "She is a member of the Academy."
        - "He plays for FC Barcelona."
        - "She belongs to the Green Party."

    Fields
    ------
    member:
        The entity that is a member / affiliate (X).
    group:
        The group / organization / party / team that X belongs to (Y).
    id:
        Optional stable identifier for this membership relation.
    relation_type:
        High-level relation label, e.g. "member", "player", "supporter".
        This is a free-form string; engines may normalize it to an
        inventory if needed.
    role_label:
        Optional more specific role label within the group, e.g.
        "goalkeeper", "board member", "senator".
    start:
        Optional time span indicating when the membership started.
    end:
        Optional time span indicating when the membership ended.
    status:
        Optional status label, e.g. "current", "former", "honorary".
    certainty:
        Confidence in the fact, between 0.0 and 1.0. Callers may keep
        this at 1.0 for asserted facts and use lower values for
        inferred / contested information.
    source_id:
        Optional identifier for the upstream source (e.g. Wikidata QID
        or statement id) that this relation was derived from.
    extra:
        Free-form metadata bag for project-specific extensions.
    """

    # Core participants (required)
    member: Entity  # X
    group: Entity  # Y

    # Optional metadata / qualifiers
    id: Optional[str] = None
    relation_type: str = "member"  # "member", "player", "supporter", …

    # Optional more specific role label, e.g. "goalkeeper"
    role_label: Optional[str] = None

    # Temporal qualifiers
    start: Optional[TimeSpan] = None
    end: Optional[TimeSpan] = None

    # Status / provenance
    status: Optional[str] = None  # "current", "former", "honorary"
    certainty: float = 1.0
    source_id: Optional[str] = None

    # Arbitrary extensions
    extra: Dict[str, Any] = field(default_factory=dict)
