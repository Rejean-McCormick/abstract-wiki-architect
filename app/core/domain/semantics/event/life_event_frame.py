# semantics\event\life_event_frame.py
# semantics/event/life_event_frame.py
#
# LifeEventFrame
# ==============
#
# High-level semantic frame for biographical “life events”.
#
# This module introduces `LifeEventFrame` as a specialized event frame for
# episodes in a person’s life such as:
#
#   - birth and death
#   - education (degrees, studies)
#   - professional appointments and roles
#   - awards and honors
#   - marriages and family milestones
#   - relocations and migrations
#
# It is implemented as a thin subclass of the generic `Event` dataclass from
# `semantics.types` and registered under the canonical frame type
# `"event.life"` in `semantics.all_frames`.
#
# The intent is to give the discourse planner and NLG engines a dedicated
# family for biographical timelines, while reusing the same underlying event
# structure (participants, time, location, properties) everywhere.
#
# Typical usage
# -------------
#
# Upstream components should construct a `LifeEventFrame` with:
#
#   - `event_type` set to a biographical subtype such as:
#       "birth", "death", "education", "appointment",
#       "award", "marriage", "relocation", ...
#   - `participants` containing at least the main person under a role like
#     "subject", "person", or "honouree" (project-specific but documented).
#   - `time` as a `TimeSpan` (year, date, or interval).
#   - `location` as a `Location`, when available.
#
# Engines can then:
#
#   - inspect `event_type` to choose phrasing templates,
#   - use the helper methods here to retrieve the main person, time, and
#     place in a uniform way,
#   - treat life events differently from non-biographical events when
#     building timelines or section structures.
#
# This module does not perform any I/O or language-specific work; it is purely
# semantic and language-neutral.

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Optional

from semantics.types import Entity, Event, Location, TimeSpan
from semantics.all_frames import register_frame_type


@register_frame_type("event.life")
@dataclass
class LifeEventFrame(Event):
    """
    Biographical life-event frame, specializing :class:`semantics.types.Event`.

    Semantics
    ---------
    `LifeEventFrame` represents an event or state that is part of a person’s
    biography. It reuses all fields from :class:`Event`:

        - id: Optional[str]
            Stable identifier for the event, if any.

        - event_type: str
            High-level label, e.g. "birth", "death", "education", "award",
            "appointment", "marriage", "relocation", "generic-life", ...

        - participants: dict[str, Entity]
            Mapping from role label → Entity. For life events, typical roles
            include:

                {
                    "subject": Entity(...),     # the person whose life this is
                    "spouse": Entity(...),
                    "employer": Entity(...),
                    "institution": Entity(...),
                    "award_giver": Entity(...),
                }

            Role labels are free-form strings but should follow a small,
            documented inventory in upstream code.

        - time: TimeSpan | None
            When the life event happened (single date or interval).

        - location: Location | None
            Where the event took place (city, country, institution, etc.).

        - properties: dict[str, Any]
            Additional structured properties, for example:

                {
                    "degree": "PhD",
                    "field_of_study": "physics",
                    "position_title": "Professor",
                    "honour_title": "Nobel Prize in Physics",
                }

        - extra: dict[str, Any]
            Arbitrary metadata for tracing back to the source JSON, including
            original IDs, raw fragments, or provenance information.

    In addition to the base fields, this class adds a stable `frame_type`
    discriminator so that the generic frame registry and routing logic can
    treat life events as their own family.

    Frame type
    ----------
    The canonical frame type string is:

        "event.life"

    This is registered in :mod:`semantics.all_frames` via the
    :func:`register_frame_type` decorator and can be used for:

        - JSON `"frame_type"` values,
        - frame-family routing in NLG engines,
        - CLI flags (e.g. `--frame-type event.life`).

    Helper properties
    -----------------
    For convenience, this class exposes a few read-only properties that make
    common queries easier and more uniform across projects:

        - `main_person`: best-effort lookup of the biographical subject.
        - `timespan`: alias for `time`.
        - `place`: alias for `location`.

    These are purely derived views and do not add new semantic content.
    """

    #: Stable frame family identifier for life events.
    frame_type: ClassVar[str] = "event.life"

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def main_person(self) -> Optional[Entity]:
        """
        Return the main person this life event is about, if detectable.

        Heuristics:
            1. Prefer a participant with role "subject".
            2. Fall back to "person" if present.
            3. Otherwise, return None.

        Projects with different role labels can still access the full
        `participants` mapping directly.
        """
        if "subject" in self.participants:
            return self.participants["subject"]
        if "person" in self.participants:
            return self.participants["person"]
        return None

    @property
    def timespan(self) -> Optional[TimeSpan]:
        """
        Alias for the underlying :class:`Event.time` field.

        This is provided mainly for readability in discourse / planning code
        that works specifically with life events.
        """
        return self.time

    @property
    def place(self) -> Optional[Location]:
        """
        Alias for the underlying :class:`Event.location` field.

        This is provided mainly for readability; no additional semantics are
        introduced beyond the base event location.
        """
        return self.location


__all__ = ["LifeEventFrame"]
