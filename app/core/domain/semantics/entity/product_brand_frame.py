# semantics\entity\product_brand_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, Location, TimeSpan


@dataclass
class ProductBrandFrame:
    """
    Semantic frame for commercial products and brands.

    This frame is intended for short encyclopedic summaries of products,
    product lines, and brands (e.g. a soft drink, a smartphone model,
    a clothing brand).

    Fields:
        main_entity:
            The entity the description is about (product or brand).
            Typically corresponds to a Wikidata item or similar ID.

        owner_entity:
            Optional owning or parent organization, e.g. the company
            that manufactures or owns the product/brand.

        product_type_lemmas:
            Language-neutral lemmas describing the product type, e.g.
            ["soft drink"], ["smartphone"], ["running shoe"].

        brand_lemmas:
            Lemmas for the brand name or brand family, if distinct from
            the product label, e.g. ["Coca-Cola"], ["iPhone"].

        market_segment_lemmas:
            High-level market/segment descriptors, e.g. ["luxury"],
            ["budget"], ["mid-range"], ["flagship"].

        launch_event:
            Optional event representing the initial launch or
            introduction of the product/brand.

        launch_time:
            Optional coarse-grained time span for the launch, if a
            full event object is not available.

        launch_location:
            Optional location of the initial launch (country, city,
            region, etc.).

        regions_of_sale:
            List of locations where the product/brand is (or was)
            marketed or sold, typically countries or regions.

        discontinued_time:
            Optional time span representing when the product/brand was
            discontinued, if applicable.

        attributes:
            Free-form semantic attributes for the product/brand, e.g.:
                {
                    "form_factor": ["smartphone"],
                    "os": ["android"],
                    "flavors": ["cola", "cherry"],
                    "target_audience": ["children", "families"],
                }

        extra:
            Arbitrary metadata or original source structure, kept
            opaque to the NLG layer.
    """

    main_entity: Entity
    owner_entity: Optional[Entity] = None

    product_type_lemmas: List[str] = field(default_factory=list)
    brand_lemmas: List[str] = field(default_factory=list)
    market_segment_lemmas: List[str] = field(default_factory=list)

    launch_event: Optional[Event] = None
    launch_time: Optional[TimeSpan] = None
    launch_location: Optional[Location] = None

    regions_of_sale: List[Location] = field(default_factory=list)
    discontinued_time: Optional[TimeSpan] = None

    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    # Stable identifier for this frame family, for routing / introspection.
    frame_type: str = field(init=False, default="entity.product_brand")


__all__ = ["ProductBrandFrame"]
