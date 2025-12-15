# semantics\__init__.py
from __future__ import annotations

"""
semantics
=========

Convenience facade for the semantic data structures and helpers used by
Abstract Wiki Architect.

Typical usage:

    from semantics import (
        Entity,
        Location,
        TimeSpan,
        Event,
        BioFrame,
        SemanticFrame,
        BioSemantics,
        InfoStructure,
        normalize_bio_semantics,
        normalize_info_structure,
        roles,
    )

Lower-level modules remain available under the package:

    import semantics.types
    import semantics.normalization
    import semantics.roles
"""

from .types import Entity, Location, TimeSpan, Event, BioFrame, SemanticFrame
from .normalization import (
    BioSemantics,
    InfoStructure,
    normalize_gender,
    normalize_info_structure,
    normalize_bio_semantics,
    normalize_bio_with_info,
)
from . import roles


__all__ = [
    # Core semantic units
    "Entity",
    "Location",
    "TimeSpan",
    # Events and frames
    "Event",
    "BioFrame",
    "SemanticFrame",
    # Normalization types & helpers
    "BioSemantics",
    "InfoStructure",
    "normalize_gender",
    "normalize_info_structure",
    "normalize_bio_semantics",
    "normalize_bio_with_info",
    # Roles module (kept as a module, not star-imported)
    "roles",
]
