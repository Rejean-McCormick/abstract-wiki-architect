# semantics\relational\relation_bundle_frame.py
"""
semantics/relational/relation_bundle_frame.py
---------------------------------------------

Relation-bundle / multi-fact frame.

This module defines a high-level frame for packaging several closely
related relational facts about the same subject into a single semantic
object. The typical use case is to generate short, information-dense
sentences like:

    - "Paris is the capital and most populous city of France,
       with a population of about 2.1 million people."
    - "Zurich is the largest city in Switzerland and the capital
       of the canton of Zurich, with a population of …"

Rather than forcing downstream components to juggle multiple small
frames (definition, attribute, quantitative measure, membership, etc.)
in isolation, we let them arrive pre-grouped as a bundle.

The bundle itself is language-independent; any choices about how many
facts to realize in one sentence, and in what order, are handled by
the NLG layer (discourse planner / construction selection).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity
from semantics.normalization import InfoStructure


@dataclass
class RelationBundleItem:
    """
    One component relation inside a RelationBundleFrame.

    The `relation` field is intended to hold a *relational frame* such as:

        - a membership / affiliation frame
        - a definition / classification frame
        - an attribute / property frame
        - a quantitative measure frame
        - a part–whole frame
        - etc.

    This module does not prescribe which exact frame types are allowed;
    projects can maintain their own inventory and routing rules. The
    only assumption is that the relation "says something about" the
    same `subject` as the parent bundle.

    Fields
    ------

    relation_type:
        Coarse label describing the kind of relation, used for ordering
        and surface-planning heuristics, e.g.:

            "definition"
            "classification"
            "attribute"
            "quantitative"
            "membership"
            "part_whole"
            "location"
            "role"

        This is a free-form string; planners may normalize it to a
        canonical inventory if desired.

    relation:
        Underlying relation object. In a full system this is typically
        one of the more specific relational frames (membership,
        quantitative measure, etc.), but for maximal flexibility it is
        typed as `Any`.

    salience:
        Optional numeric score indicating how important this relation is
        within the bundle. Higher values mean "more important". This is
        a hint for planners deciding which items to include in very
        short outputs.

    order_hint:
        Optional integer used to suggest a preferred ordering among
        relations of similar type. Lower values are typically placed
        earlier. When absent, planners are free to impose their own
        ordering.
    """

    relation_type: str
    relation: Any
    salience: float = 1.0
    order_hint: Optional[int] = None


@dataclass
class RelationBundleFrame:
    """
    Bundle of related relational facts about a single subject.

    Typical examples include:

        - Definition + location + population
        - Definition + membership + ranking
        - Definition + attribute + quantitative measures

    This frame does **not** require that all items be realized in a
    single sentence; it simply guarantees that the relations in
    `items` are closely related and *could* be realized together if the
    discourse planner decides to do so.

    Fields
    ------

    frame_type:
        Stable string label used by routers / planners to recognize this
        as a relation-bundle frame. For this module we use
        `"rel.bundle"`.

    subject:
        The entity about which the bundle of facts is stated, e.g. a
        city, country, organization, or person.

    items:
        List of `RelationBundleItem` entries. Each item wraps a more
        specific relational frame together with a coarse `relation_type`
        and optional salience / ordering hints.

        All items are expected (by convention) to be semantically about
        `subject`, even if the underlying frames contain more complex
        structures (events, participants, etc.).

    info_structure:
        Optional information-structure annotation indicating which roles
        (e.g. subject vs. predicate NPs) should be treated as topic,
        focus, or background. This is entirely optional; if omitted,
        planners and engines fall back to their default strategies.

    attributes:
        Open-ended attribute map for bundle-level metadata that may be
        useful to downstream components, such as:

            {
                "max_items_per_sentence": 3,
                "preferred_pattern": "definition_plus_measure",
            }

        The schema here is intentionally unspecified; values should be
        JSON-serializable.

    extra:
        Free-form metadata that is preserved but not interpreted by the
        core NLG logic (e.g. original statement IDs, provenance, or
        pipeline-debug information).
    """

    frame_type: str = field(init=False, default="rel.bundle")
    subject: Entity = field(default_factory=Entity)
    items: List[RelationBundleItem] = field(default_factory=list)
    info_structure: Optional[InfoStructure] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["RelationBundleItem", "RelationBundleFrame"]
