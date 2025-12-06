"""
tests/http_api/test_frames_registry.py
-------------------------------------

Sanity checks for the HTTP-facing frame registry in
:mod:`architect_http_api.registry.frames_registry`.

These tests verify that the registry:

* Exposes at least all semantic frame families from :mod:`semantics.all_frames`.
* Preserves the canonical, documented ordering of frame_type strings within each
  family.
* Does not introduce duplicate frame_type entries within a family.
"""

from __future__ import annotations

from typing import List

from architect_http_api.registry import frames_registry
from semantics.all_frames import FRAME_FAMILIES, FrameType


def test_registry_exposes_all_semantic_families() -> None:
    """
    Every family key present in FRAME_FAMILIES must be exposed by the
    HTTP-layer registry.
    """
    families_from_registry = set(frames_registry.list_families())

    for family in FRAME_FAMILIES.keys():
        assert family in families_from_registry, f"Missing family in registry: {family}"


def test_family_members_match_semantic_catalogue_in_order() -> None:
    """
    For each frame family, the registry must return the same list of
    frame_type strings, in the same canonical order as FRAME_FAMILIES.
    """
    for family, expected_types in FRAME_FAMILIES.items():
        registry_types: List[FrameType] = frames_registry.get_family_frame_types(family)
        assert registry_types == expected_types, f"Family {family} mismatch"


def test_family_members_are_unique_in_registry() -> None:
    """
    Within each family, the registry must not introduce duplicate frame_type
    entries.
    """
    for family in frames_registry.list_families():
        frame_types = frames_registry.get_family_frame_types(family)
        assert len(frame_types) == len(
            set(frame_types)
        ), f"Duplicate frame_type values in family {family}"
