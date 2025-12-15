# semantics\entity\chemical_material_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity
from semantics.common.quantity import Quantity


@dataclass
class ChemicalMaterialFrame:
    """
    Semantic frame for a single chemical substance or material.

    This frame is intended for short encyclopedic descriptions such as:
        - "Sodium chloride is an ionic compound with the formula NaCl."
        - "Graphene is an allotrope of carbon consisting of a single layer
          of atoms arranged in a hexagonal lattice."

    Fields:
        entity:
            The underlying entity this frame describes (e.g. the Wikidata
            item for the compound or material). This is the anchor used by
            other layers to find labels, IDs, and links.
        formula:
            Preferred chemical formula (ASCII or Unicode), e.g. "NaCl",
            "C6H6", "H₂O".
        iupac_name:
            IUPAC systematic name, if available (e.g. "sodium chloride").
        common_names:
            List of common names and synonyms (e.g. ["table salt"]).
            These are language-neutral labels; the generator or lexicon
            chooses appropriate localized forms.
        phase_at_stp:
            Aggregate state at standard temperature and pressure, e.g.
            "solid", "liquid", "gas", "plasma". Free string but expected
            to be one of a small inventory.
        appearance:
            Short free-form description of appearance, e.g. "white
            crystalline solid", "colorless gas".
        molar_mass:
            Molar mass represented as a Quantity. Units are typically
            g/mol or kg/mol; the unit string is carried by the Quantity.
        density:
            Density near room conditions, represented as a Quantity
            (e.g. g/cm³, kg/m³).
        melting_point:
            Melting point represented as a temperature Quantity
            (e.g. in °C or K, as encoded in the Quantity).
        boiling_point:
            Boiling point represented as a temperature Quantity.
        categories:
            High-level classification labels, such as "alkali metal",
            "halide salt", "polymer", "alloy", "organic solvent".
        uses:
            List of salient applications / uses as short phrases,
            e.g. ["food seasoning", "de-icing roads"].
        hazards:
            List of salient hazards or safety concerns, expressed as
            short phrases, e.g. ["corrosive", "oxidizer", "toxic if inhaled"].
        extra:
            Arbitrary metadata or source-specific payload, e.g. original
            Wikidata statements, IDs, or mapping info.

        frame_type:
            Constant identifier for this frame family. Always
            "chemical_material". Exposed primarily for routing and
            introspection; not intended to be modified by callers.
    """

    # Core identification
    entity: Entity

    # Names and labels
    formula: Optional[str] = None
    iupac_name: Optional[str] = None
    common_names: List[str] = field(default_factory=list)

    # Basic physical description
    phase_at_stp: Optional[str] = None
    appearance: Optional[str] = None

    # Physical quantities
    molar_mass: Optional[Quantity] = None
    density: Optional[Quantity] = None
    melting_point: Optional[Quantity] = None
    boiling_point: Optional[Quantity] = None

    # Classification and usage
    categories: List[str] = field(default_factory=list)
    uses: List[str] = field(default_factory=list)
    hazards: List[str] = field(default_factory=list)

    # Free-form extension hook
    extra: Dict[str, Any] = field(default_factory=dict)

    # Frame protocol hook (not part of __init__)
    frame_type: str = field(init=False, default="chemical_material")


__all__ = ["ChemicalMaterialFrame"]
