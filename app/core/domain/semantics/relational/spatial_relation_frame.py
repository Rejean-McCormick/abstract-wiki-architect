# semantics\relational\spatial_relation_frame.py
# semantics/relational/spatial_relation_frame.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from semantics.types import Entity, TimeSpan
from semantics.common.quantity import Quantity


@dataclass
class SpatialRelationFrame:
    """
    Spatial relationship between entities/places.

    Purpose
    -------
    Encode simple spatial relations such as:

    - Inclusion (“in”, “inside”)
    - Relative position (“north of”, “near”)
    - Distance when needed

    Typical realizations include:

        - "The city is located in northern Italy."
        - "The river flows through the city."
        - "The island lies 50 km off the coast."

    Fields
    ------

    id:
        Optional stable identifier for the relation instance (e.g. a row
        ID or source key).

    subject:
        The entity / place that is being located (X).

    reference:
        The reference entity / place (Y), often a country, region, or
        another geographic feature.

    relation:
        Coarse relation label such as:

            "in", "within", "inside",
            "near", "adjacent_to",
            "north_of", "south_of", "east_of", "west_of",
            "on", "along", "at_the_mouth_of", ...

        The inventory is intentionally open; downstream code may map
        project-specific labels into a smaller canonical set.

    distance:
        Optional numeric distance between `subject` and `reference`,
        represented as a `Quantity` (e.g. 50 km).

    region_lemma:
        Optional lemma describing a subregion or part of the reference,
        e.g. "northern", "southern", "eastern", "central". Used for
        patterns like "in northern Italy" or "in central France".

    time:
        Optional `TimeSpan` indicating when the relation holds (for
        time-sensitive locative relations).

    certainty:
        Confidence value in [0, 1], where 1.0 means full confidence.
        This can be used by higher-level components to downweight or
        omit low-certainty relations.

    source_id:
        Optional opaque identifier for the source statement or triple,
        useful for debugging and traceability.

    extra:
        Free-form metadata bag for additional information that is not
        widely shared across projects. Values should be JSON-serializable.
    """

    id: Optional[str] = None

    subject: Entity = field(default_factory=Entity)
    reference: Entity = field(default_factory=Entity)
    relation: str = ""

    # Optional quantitative / regional detail
    distance: Optional[Quantity] = None
    region_lemma: Optional[str] = None

    time: Optional[TimeSpan] = None
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["SpatialRelationFrame"]
