# semantics\narrative\structure_organization_frame.py
"""
semantics/narrative/structure_organization_frame.py
---------------------------------------------------

Narrative-level frame for describing the internal structure or
organization of a complex entity, such as:

    - States and governments (executive / legislative / judicial branches)
    - Corporations and holding groups (divisions, subsidiaries)
    - Universities (faculties, schools, departments)
    - Large NGOs or international organizations

The goal of this frame is to provide a language-neutral representation
from which multi-clause descriptions like the following can be
generated:

    - "The government of X is a federal parliamentary system consisting
       of executive, legislative, and judicial branches."
    - "Company X is organized into three main divisions: A, B, and C."
    - "The university is divided into several faculties, including the
       Faculty of Arts and the Faculty of Science."

Surface realization (exact wording, clause ordering, connectives) is
handled by constructions and engines elsewhere in the NLG pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity


@dataclass
class OrganizationalUnitNode:
    """
    Node representing a unit within an organization's internal structure.

    Each unit corresponds to some identifiable part of the organization
    (e.g. "executive branch", "senate", "board of directors",
    "faculty of science").

    Fields
    ------

    entity:
        Entity representing the unit itself. For many units, this will
        be a dedicated article-level entity with its own ID and name
        (e.g. "European Commission"), but in smaller structures it may
        simply reuse the parent entity with a different role label.

    parent_key:
        Optional key referencing the unit's parent in the structure
        (see ``StructureOrganizationFrame.unit_index_key``). This
        allows representing hierarchical structures as trees or DAGs.

        If None, the unit is considered "top-level" in the structure
        (e.g. a branch of government, a main division).

    key:
        Stable, local identifier for this unit node *within the
        structure frame*. It is used as the target of ``parent_key``
        references. Typical values might reuse an entity id or a short
        slug such as "executive", "legislative", "judicial",
        "north_division", etc.

    unit_type_lemmas:
        Lemma-level labels describing the *kind* of unit, for example:

            ["branch"]
            ["ministry"]
            ["department"]
            ["division"]
            ["faculty"]

        These are language-neutral identifiers that the lexicon can map
        to surface words per language.

    responsibility_lemmas:
        Lemma-level labels for the main functional area(s) of this unit,
        e.g.:

            ["foreign affairs"]
            ["defense"]
            ["research"]
            ["undergraduate education"]

        Engines may choose to realize these as prepositional phrases or
        content clauses (e.g. "responsible for foreign affairs").

    role_labels:
        List of functional roles this unit plays (e.g., "executive", "advisory").

    attributes:
        Arbitrary JSON-like attribute map for additional structured
        information about the unit, such as:

            {
                "seat_location_id": "Q12345",
                "member_count": 435,
                "elected": True
            }

    extra:
        Free-form metadata not interpreted by language-neutral NLG
        logic. This is intended for provenance, internal IDs, or raw
        source snippets.
    """

    entity: Optional[Entity] = None
    key: str = ""
    parent_key: Optional[str] = None

    unit_type_lemmas: List[str] = field(default_factory=list)
    responsibility_lemmas: List[str] = field(default_factory=list)

    # Required by tests
    role_labels: List[str] = field(default_factory=list)

    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructureOrganizationFrame:
    """
    Narrative frame describing the internal structure / organization of
    a complex entity.

    Core identity
    -------------

    frame_type:
        Stable label used by routers / planners to recognize this
        narrative family. The canonical value for this frame is:

            "narr.structure-organization"

    main_entity:
        The organization / state / institution whose internal structure
        is being described (e.g. a country, a company, a university).

    structure_type_lemmas:
        Lemma-level labels describing the overall *type* of structure,
        such as:

            ["federal system"]
            ["unitary state"]
            ["parliamentary system"]
            ["presidential system"]
            ["holding company structure"]

        These help choose higher-level descriptions like "X is a federal
        parliamentary system" or "X is organized as a holding company".

    unit_index_key:
        Name of the attribute in :class:`OrganizationalUnitNode` that is
        used as a key for parent-child relations. In most cases this
        should be ``"key"`` and can be left as the default.

        This field exists to make it explicit how parent references in
        nodes should be interpreted, and to allow future flexibility
        (e.g. using external IDs instead).

    units:
        List of :class:`OrganizationalUnitNode` objects describing the
        internal units and their relationships (parent-child via
        ``parent_key``). Engines can interpret this list as:

            - a forest of trees (for purely hierarchical structures),
            - or a more general directed graph (for cross-cutting units).

        For many texts, it is sufficient to identify top-level units and
        optionally a second tier.

    key_positions:
        Mapping from role label → list of Entities representing
        *persons* or *bodies* that play a key role in the structure, for
        example:

            {
                "head_of_state": [Entity(...)]
                "head_of_government": [Entity(...)]
                "board_of_directors": [Entity(...)]
            }

        This is primarily useful when generating richer descriptions
        that mention office-holders alongside the abstract structure.

    attributes:
        Arbitrary JSON-like attribute map for structure-level properties,
        such as:

            {
                "chambers": 2,
                "is_bicameral": True,
                "has_written_constitution": True
            }

    extra:
        Free-form metadata bag passed through unchanged, intended for
        provenance and debugging, not interpreted by language-neutral
        NLG logic.
    """

    # Using field(init=False) to include in asdict() but exclude from __init__
    # Matches the exact test expectation "narr.structure-organization"
    frame_type: str = field(default="narr.structure-organization", init=False)

    # Entity whose internal structure is being described
    main_entity: Optional[Entity] = None

    # Overall structure type / classification
    structure_type_lemmas: List[str] = field(default_factory=list)

    # How to interpret keys in OrganizationalUnitNode.parent_key
    unit_index_key: str = "key"

    # Internal units
    units: List[OrganizationalUnitNode] = field(default_factory=list)

    # Key positions / roles mapped to entities (people or bodies)
    key_positions: Dict[str, List[Entity]] = field(default_factory=dict)

    # Generic extension points
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["OrganizationalUnitNode", "StructureOrganizationFrame"]
