# semantics\entity\person_frame.py
# semantics/entity/person_frame.py
#
# PersonFrame
# ===========
#
# High-level semantic frame for person / biography-style entities.
#
# This module introduces `PersonFrame` as an explicit frame type for
# person articles. It is a thin subclass of `BioFrame` from
# `semantics.types`, adding a stable `frame_type` attribute so it fits
# into the general frame-family machinery defined in `semantics.all_frames`.
#
# Existing code that already uses `BioFrame` continues to work; this
# class simply provides a more explicitly named alias and a canonical
# `frame_type` ("bio") for routing and registry purposes.

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from semantics.types import BioFrame
from semantics.all_frames import register_frame_type


@register_frame_type("bio", override=True)
@dataclass
class PersonFrame(BioFrame):
    """
    PersonFrame

    A specialization of `BioFrame` representing a person / biography
    entity frame.

    Semantics
    ---------
    This frame is intended for first-sentence, Wikipedia-style person
    leads, and mirrors the fields of `BioFrame`:

        - main_entity: Entity
            The person the biography is about.

        - primary_profession_lemmas: list[str]
            Lemmas for the main profession(s) ("physicist", "writer"...).

        - nationality_lemmas: list[str]
            Lemmas for nationality adjectives ("polish", "french"...).

        - birth_event: Event | None
            Optional birth event.

        - death_event: Event | None
            Optional death event.

        - other_events: list[Event]
            Other salient life events (discoveries, awards, appointments…).

        - attributes: dict[str, Any]
            Miscellaneous attributes such as "field", "known_for", etc.

        - extra: dict[str, Any]
            Arbitrary metadata (IDs, provenance, raw JSON fragments, etc.).

    The only addition compared to `BioFrame` is the explicit `frame_type`
    class attribute, which allows generic NLG APIs to branch on the
    string `"bio"` when performing routing.
    """

    #: Stable frame type string used by the generic Frame protocol and
    #: by the registry in `semantics.all_frames`.
    frame_type: ClassVar[str] = "bio"


__all__ = ["PersonFrame"]
