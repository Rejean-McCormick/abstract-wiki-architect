"""
qa/test_frames_entity.py
------------------------

Basic unit tests for the entity frame catalogue in :mod:`semantics.all_frames`.

These tests focus on the *frame type inventory* and family mapping for
entity frames (things we can write articles about). They do not exercise the
full entity-frame dataclasses or any NLG behaviour; those are covered elsewhere.
"""

from __future__ import annotations

from typing import Dict, List

from semantics.all_frames import (
    FRAME_FAMILIES,
    FRAME_FAMILY_MAP,
    FrameFamily,
    FrameType,
    family_for_frame,
)


def test_entity_family_is_present() -> None:
    """The 'entity' family must be present in FRAME_FAMILIES."""
    assert "entity" in FRAME_FAMILIES

    entity_types = FRAME_FAMILIES["entity"]
    assert isinstance(entity_types, list)
    assert len(entity_types) > 0


def test_entity_family_members_are_canonical_and_ordered() -> None:
    """
    The entity family should contain exactly the expected frame types in
    a stable, documented order (see docs/FRAMES_ENTITY.md and
    semantics/all_frames.py).
    """
    expected: List[FrameType] = [
        # 1. Person / Biography frame – existing BioFrame
        "bio",
        # 2. Organization / Group frame
        "entity.organization",
        # 3. Geopolitical entity frame
        "entity.gpe",
        # 4. Other place / geographic feature frame
        "entity.place",
        # 5. Facility / infrastructure frame
        "entity.facility",
        # 6. Astronomical object frame
        "entity.astronomical_object",
        # 7. Species / taxon frame
        "entity.taxon",
        # 8. Chemical / material frame
        "entity.chemical",
        # 9. Physical object / artifact frame
        "entity.artifact",
        # 10. Vehicle / craft frame
        "entity.vehicle",
        # 11. Creative work frame
        "entity.creative_work",
        # 12. Software / website / protocol / standard frame
        "entity.software_or_standard",
        # 13. Product / brand frame
        "entity.product_or_brand",
        # 14. Sports team / club frame
        "entity.sports_team",
        # 15. Competition / tournament / league frame
        "entity.competition",
        # 16. Language frame
        "entity.language",
        # 17. Religion / belief system / ideology frame
        "entity.belief_system",
        # 18. Academic discipline / field / theory frame
        "entity.academic_discipline",
        # 19. Law / treaty / policy / constitution frame
        "entity.law_or_treaty",
        # 20. Project / program / initiative frame
        "entity.project_or_program",
        # 21. Fictional entity / universe / franchise frame
        "entity.fictional_entity",
    ]

    entity_types = FRAME_FAMILIES["entity"]
    assert entity_types == expected


def test_entity_family_members_are_unique() -> None:
    """No duplicate entity frame_type strings in the catalogue."""
    entity_types = FRAME_FAMILIES["entity"]
    assert len(entity_types) == len(set(entity_types))


def test_entity_types_map_back_to_entity_family() -> None:
    """
    FRAME_FAMILY_MAP must map each entity frame_type back to the 'entity'
    family.
    """
    for ft in FRAME_FAMILIES["entity"]:
        fam: FrameFamily | None = FRAME_FAMILY_MAP.get(ft)
        assert fam == "entity"


def test_family_for_frame_works_with_entity_dicts() -> None:
    """
    family_for_frame should correctly classify dict-like frames that
    declare an entity frame_type.
    """
    samples = [
        {"frame_type": "bio"},
        {"frame_type": "entity.organization"},
        {"frame_type": "entity.creative_work"},
        {"frame_type": "entity.language"},
    ]

    for payload in samples:
        fam = family_for_frame(payload)
        assert fam == "entity"


def test_entity_frame_types_have_consistent_mapping_view() -> None:
    """
    Cross-check that the mapping view over FRAME_FAMILY_MAP for the entity
    family matches the canonical list in FRAME_FAMILIES['entity'].
    """
    # Build a reverse view from FRAME_FAMILY_MAP.
    from_map: List[FrameType] = [
        ft for ft, fam in FRAME_FAMILY_MAP.items() if fam == "entity"
    ]

    # Order is defined only by FRAME_FAMILIES; we compare as sets here.
    assert set(from_map) == set(FRAME_FAMILIES["entity"])
