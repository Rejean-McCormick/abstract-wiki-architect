"""
qa/test_frames_relational.py
----------------------------

Smoke tests for the relational / statement-level frame dataclasses.

These tests are deliberately light-weight and engine-agnostic. Their
goals are to verify that:

- Relational frame classes can be instantiated with minimal, realistic data.
- Any documented `frame_type` constants are wired as expected.
- Key container fields (lists / dicts) default to empty and can be
  populated without errors.

The frames covered here correspond (in part) to the “Relational /
statement-level” families in `docs/FRAMES_RELATIONAL.md` and
`semantics/all_frames.py`.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from semantics.types import Entity, Event, Location, TimeSpan
from semantics.relational.attribute_property_frame import AttributeFrame
from semantics.relational.definition_classification_frame import (
    DefinitionClassificationFrame,
)
from semantics.relational.membership_affiliation_frame import MembershipFrame
from semantics.relational.ownership_control_frame import OwnershipControlFrame
from semantics.relational.part_whole_composition_frame import (
    PartWholeCompositionFrame,
)
from semantics.relational.role_position_office_frame import (
    RolePositionOfficeFrame,
)
from semantics.relational.spatial_relation_frame import SpatialRelationFrame
from semantics.relational.temporal_relation_frame import TemporalRelationFrame


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_person(pid: str = "P1", name: str = "Sample Person") -> Entity:
    return Entity(id=pid, name=name, human=True, entity_type="person")


def _make_org(oid: str = "O1", name: str = "Sample Organization") -> Entity:
    return Entity(id=oid, name=name, entity_type="organization")


def _make_place(lid: str = "L1", name: str = "Sample Place") -> Entity:
    return Entity(id=lid, name=name, entity_type="place")


def _make_time_span(start_year: int, end_year: int | None = None) -> TimeSpan:
    # TimeSpan is intentionally coarse; most usages only need years.
    return TimeSpan(start_year=start_year, end_year=end_year)


# ---------------------------------------------------------------------------
# Attribute / property frame
# ---------------------------------------------------------------------------


def test_attribute_frame_basic_construction() -> None:
    subject = _make_person()
    frame = AttributeFrame(
        subject=subject,
        attribute="political_system",
        value="democratic",
    )

    assert frame.subject is subject
    assert frame.attribute == "political_system"
    assert frame.value == "democratic"

    # Optional metadata should be present but not required
    assert frame.id is None
    as_dict = asdict(frame)
    assert "subject" in as_dict
    assert "attribute" in as_dict
    assert "value" in as_dict


def test_attribute_frame_frame_type_constant() -> None:
    subject = _make_place()
    frame = AttributeFrame(subject=subject, attribute="status", value="bilingual")

    # AttributeFrame declares a simple discriminator for routing.
    assert frame.frame_type == "rel_attribute"


# ---------------------------------------------------------------------------
# Definition / classification frame
# ---------------------------------------------------------------------------


def test_definition_classification_frame_basic() -> None:
    subject = _make_place(name="Sample River")
    supertype = _make_place(name="River")

    frame = DefinitionClassificationFrame(
        subject=subject,
        supertype_entities=[supertype],
        supertype_lemmas=["river"],
    )

    assert frame.subject is subject
    assert frame.supertype_entities == [supertype]
    assert "river" in frame.supertype_lemmas

    # The frame_type is a ClassVar, but should be accessible on the class
    assert DefinitionClassificationFrame.frame_type == "rel.definition-classification"


# ---------------------------------------------------------------------------
# Membership / affiliation frame
# ---------------------------------------------------------------------------


def test_membership_frame_basic_construction() -> None:
    member = _make_person()
    group = _make_org(name="Sample Club")

    frame = MembershipFrame(member=member, group=group)

    assert frame.member is member
    assert frame.group is group
    # Default relation type is a simple “member” label
    assert frame.relation_type == "member"
    # Optional qualifiers
    assert frame.start is None
    assert frame.end is None

    # It should be JSON-serializable via asdict
    data = asdict(frame)
    assert data["member"]["name"] == member.name
    assert data["group"]["name"] == group.name


# ---------------------------------------------------------------------------
# Ownership / control frame
# ---------------------------------------------------------------------------


def test_ownership_control_frame_basic_construction() -> None:
    owner = _make_org(oid="O_OWNER", name="Owner Corp")
    asset = _make_org(oid="O_ASSET", name="Asset Ltd")

    frame = OwnershipControlFrame(owner=owner, asset=asset)

    assert frame.owner is owner
    assert frame.asset is asset
    assert frame.relation_type == "ownership"
    # Optional quantitative fields default to None
    assert frame.ownership_share_pct is None
    # The frame discriminator for routing
    assert frame.frame_type == "relation.ownership"


def test_ownership_control_frame_with_share() -> None:
    owner = _make_org()
    asset = _make_org(oid="O_TARGET", name="Target Co")

    frame = OwnershipControlFrame(
        owner=owner,
        asset=asset,
        ownership_share_pct=51.0,
        control_level="majority",
    )

    assert frame.ownership_share_pct == 51.0
    assert frame.control_level == "majority"


# ---------------------------------------------------------------------------
# Part–whole / composition frame
# ---------------------------------------------------------------------------


def test_part_whole_composition_basic() -> None:
    whole = _make_place(name="Sample Country")
    region1 = _make_place(lid="R1", name="Region One")
    region2 = _make_place(lid="R2", name="Region Two")

    frame = PartWholeCompositionFrame(whole=whole)
    assert frame.whole is whole
    assert frame.parts == []

    # Can add parts after construction
    frame.parts.extend([region1, region2])
    assert len(frame.parts) == 2
    assert {p.id for p in frame.parts} == {"R1", "R2"}


# ---------------------------------------------------------------------------
# Role / position / office frame
# ---------------------------------------------------------------------------


def test_role_position_office_basic() -> None:
    holder = _make_person(pid="P_LEADER", name="Sample Leader")
    org = _make_org(oid="O_COUNTRY", name="Sample Country")

    frame = RolePositionOfficeFrame(
        office_holder=holder,
        role_lemmas=["president"],
        organization=org,
        term=_make_time_span(2000, 2008),
    )

    assert frame.office_holder is holder
    assert "president" in frame.role_lemmas
    assert frame.organization is org
    assert frame.term is not None
    assert frame.term.start_year == 2000
    assert frame.term.end_year == 2008


# ---------------------------------------------------------------------------
# Spatial relation frame
# ---------------------------------------------------------------------------


def test_spatial_relation_frame_defaults_and_update() -> None:
    # SpatialRelationFrame provides default Entities, so construction
    # without arguments should be possible.
    frame = SpatialRelationFrame()

    # Defaults
    assert isinstance(frame.subject, Entity)
    assert isinstance(frame.reference, Entity)
    assert frame.relation == ""

    # After populating, fields should reflect the new values
    subject = _make_place(name="Town A")
    reference = _make_place(name="Region B")

    frame.subject = subject
    frame.reference = reference
    frame.relation = "in"

    assert frame.subject is subject
    assert frame.reference is reference
    assert frame.relation == "in"


# ---------------------------------------------------------------------------
# Temporal relation frame
# ---------------------------------------------------------------------------


def test_temporal_relation_frame_basic() -> None:
    left_event = Event(
        id="E1",
        event_type="founding",
        participants={"subject": _make_org()},
        time=_make_time_span(1900),
    )
    right_event = Event(
        id="E2",
        event_type="expansion",
        participants={"subject": _make_org(oid="O2", name="Subsidiary")},
        time=_make_time_span(1950),
    )

    frame = TemporalRelationFrame(
        left=left_event,
        right=right_event,
        relation="before",
        left_time=left_event.time,
        right_time=right_event.time,
    )

    assert frame.left is left_event
    assert frame.right is right_event
    assert frame.relation == "before"
    assert frame.left_time is left_event.time
    assert frame.right_time is right_event.time
    assert frame.certainty == pytest.approx(1.0)
