# semantics\narrative\comparison_set_contrast_frame.py
"""
semantics/narrative/comparison_set_contrast_frame.py
----------------------------------------------------

Narrative-level frame for comparison / contrast between a *set* of
entities along one or more shared dimensions.

Typical uses include:

    - "X, Y, and Z are three major banks in A."
    - "Among the cities of X, Y has the largest population."
    - "X is larger than Y but smaller than Z."
    - "A, B, and C differ in their political systems."

The frame is language-neutral. It captures:

    - the *set* of entities being compared,
    - the dimensions / metrics along which they are compared,
    - optional ranking / ordering information,
    - optional focus / highlight entity (often the article subject).

Surface realization (choice of constructions such as "largest", "second
largest", "unlike", "whereas", etc.) is handled by downstream engines
and constructions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from semantics.types import Entity, Location


@dataclass
class ComparisonItem:
    """
    One member of a comparison set.

    Fields
    ------

    entity:
        The entity being compared (city, country, bank, team, etc.).

    role_label:
        Optional short role label describing this entity's position in
        the comparison, e.g.:

            "largest"
            "smallest"
            "second-largest"
            "outlier"
            "typical"

        This is mainly a planning hint; engines may map such labels to
        language-specific constructions.

    rank:
        Optional rank within the set (1-based by convention), typically
        with respect to a primary metric. For example, in a list of
        cities ordered by population, the largest city has `rank = 1`,
        the second-largest has `rank = 2`, and so on.

        Whether rank 1 is "best" or "worst" is determined by the parent
        frame's `order_direction` and/or semantics of the metric.

    metric_values:
        Mapping from metric identifier → value for this entity, for
        example:

            {
                "population": 1500000,
                "area_km2": 200.5,
                "gdp_usd_billion": 45.3
            }

        Metric identifiers are free-form strings; their interpretation
        is given by the parent frame (e.g. through `metric_lemmas`).

    attributes:
        Arbitrary JSON-like attributes specific to this item which are
        relevant in the context of comparison but not necessarily
        numeric, for example:

            {
                "capital": True,
                "type": "coastal city"
            }

    extra:
        Free-form metadata for provenance, IDs, raw input, etc. Not
        interpreted by language-neutral NLG logic.
    """

    entity: Entity
    role_label: Optional[str] = None
    rank: Optional[int] = None
    metric_values: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    # Optional notes field (implied by typical usage, though not strictly in test snippet)
    notes: Optional[str] = None


@dataclass
class ComparisonSetContrastFrame:
    """
    Narrative frame describing a comparison / contrast between several
    entities along one or more dimensions.

    Core identity
    -------------

    frame_type:
        Stable label used by routers / planners to recognize this
        narrative family. The canonical value is:

            "narr.comparison-set-contrast"

    items:
        List of :class:`ComparisonItem` objects, one per entity in the
        comparison set. The order of items is not semantically binding
        (unless `order_direction` and `primary_metric_id` explicitly
        indicate that the list is already sorted), but many pipelines
        will keep items in a meaningful order.

    focus_entity:
        Optional entity to highlight in the comparison, typically the
        article subject. This allows constructions such as:

            "Among the cities of X, Y is the largest."

        where Y is the `focus_entity` and the items list includes
        other cities for context.

    Comparison dimensions
    ---------------------

    metrics:
        Metadata about the metrics used in `metric_values`. This dictionary
        maps metric IDs (e.g., "population") to their metadata (unit, description).

        Example:
            {
                "population": {
                    "unit": "inhabitants",
                    "description": "City population"
                }
            }

    metric_ids:
        List of metric identifiers used in `ComparisonItem.metric_values`.
        (Kept for compatibility/redundancy with keys of `metrics`).

    metric_lemmas:
        Lemma-level labels corresponding to the metrics, suitable for
        realization.

    primary_metric_id:
        Optional identifier of the primary metric for ranking (e.g.
        "population"). If provided, engines can prefer this metric
        when generating statements such as "largest by population".

    order_direction:
        Optional direction of ordering with respect to the primary
        metric (or implicit metric if `primary_metric_id` is omitted):

            "descending"  – higher values rank earlier (e.g. population)
            "ascending"   – lower values rank earlier (e.g. rank number)
            "mixed"       – ordering is not purely monotonic / numeric

        This informs phrase choices like "largest", "smallest", "highest",
        "lowest", etc.

    comparison_type:
        Coarse label indicating what sort of comparison is intended.
        Suggested values include:

            "ranking"     – emphasize ordered ranking ("largest", "second")
            "grouping"    – emphasize membership in a set ("three major X")
            "contrast"    – emphasize differences ("unlike A, B is ...")
            "summary"     – general comparative summary without strong
                            ordering.

        This can help the planner pick templates such as "X, Y, and Z
        are three major banks in A" vs. "X is larger than Y but smaller
        than Z".

    Scope and context
    -----------------

    set_label_lemmas:
        Lemma-level labels for the kind of entities being compared,
        e.g.:

            ["city"]
            ["bank"]
            ["football club"]

        Useful for phrases like "three major banks" or "the largest
        cities".

    scope_locations:
        List of :class:`Location` describing the geographic / political
        scope of the comparison. (Note: Previously `scope_location`).

    scope_lemmas:
        Additional lemma-level hints describing scope that may not map
        neatly to a single `Location`, such as:

            ["in the European Union"]
            ["among OECD countries"]

    Generic extension points
    ------------------------

    attributes:
        Arbitrary JSON-like attributes at the frame level, for example:

            {
                "source": "World Bank 2022 estimates",
                "contains_all_major_banks": True
            }

    extra:
        Free-form metadata bag not interpreted by language-neutral NLG
        logic. Intended for provenance, debugging, or links back to
        upstream structures.
    """

    # Stable label used for routing / schema identification
    # Test expects ClassVar behavior
    frame_type: ClassVar[str] = "narr.comparison-set-contrast"

    # Items in the comparison set
    items: List[ComparisonItem] = field(default_factory=list)

    # Optional entity to highlight
    focus_entity: Optional[Entity] = None

    # Metrics / dimensions
    # Added metrics field required by test
    metrics: Dict[str, Any] = field(default_factory=dict)

    metric_ids: List[str] = field(default_factory=list)
    metric_lemmas: List[str] = field(default_factory=list)
    primary_metric_id: Optional[str] = None
    order_direction: Optional[str] = None  # "ascending", "descending", "mixed"
    comparison_type: Optional[str] = (
        None  # "ranking", "grouping", "contrast", "summary"
    )

    # Test adds time_period_label
    time_period_label: Optional[str] = None

    # Scope and context
    set_label_lemmas: List[str] = field(default_factory=list)

    # Updated to list to match test expectation "scope_locations=[...]"
    scope_locations: List[Location] = field(default_factory=list)

    scope_lemmas: List[str] = field(default_factory=list)

    # Generic extension points
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ComparisonItem", "ComparisonSetContrastFrame"]
