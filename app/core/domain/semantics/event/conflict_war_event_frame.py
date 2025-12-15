# semantics\event\conflict_war_event_frame.py
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from semantics.types import Event


@dataclass
class ConflictWarEventFrame(Event):
    """
    Event frame for conflicts, battles, wars, and military operations.

    This is a thin semantic wrapper over :class:`semantics.types.Event`
    with a canonical ``frame_type`` and a documented set of conventional
    participant roles and properties.

    Canonical frame_type
    --------------------
    * ``frame_type = "event.conflict-event"``

    Relationship to the core Event type
    -----------------------------------
    The underlying fields are inherited from :class:`Event`:

    * ``id`` – stable identifier, if any (e.g. QID or local ID).
    * ``event_type`` – high-level label (e.g. ``"war"``, ``"battle"``,
      ``"military-operation"``). Projects are free to define their own
      inventory; for conflicts, values such as ``"war"``, ``"battle"``,
      ``"siege"``, or ``"campaign"`` are typical.
    * ``participants: dict[str, Entity]`` – mapping from role label to
      :class:`Entity`.
    * ``time: TimeSpan | None`` – when the conflict occurred.
    * ``location: Location | None`` – primary location (theater, region,
      city, etc.).
    * ``properties: dict[str, Any]`` – structured conflict-specific
      details.
    * ``extra: dict[str, Any]`` – arbitrary metadata (original source
      representation, IDs, etc.).

    Recommended participant role labels
    -----------------------------------
    The ``participants`` mapping should use consistent role labels,
    for example:

    * ``"belligerent_a"``, ``"belligerent_b"`` – main opposing sides.
    * ``"belligerent_c"`` / ``"belligerent_d"`` – additional parties when
      needed.
    * ``"attacker"``, ``"defender"`` – for asymmetric engagements.
    * ``"commander_a"``, ``"commander_b"`` – key commanders per side.
    * ``"allied_force"`` / ``"opposing_force"`` – higher-level coalitions.
    * ``"civilian_population"`` – affected civilian group, if modeled.

    Recommended properties
    ----------------------
    Conflict-specific information should be stored in the generic
    ``properties`` dictionary, using keys such as:

    * ``"result"`` – textual summary of the outcome
      (e.g. ``"decisive victory for belligerent_a"``).
    * ``"outcome_type"`` – normalized label such as
      ``"victory"``, ``"defeat"``, ``"stalemate"``, ``"ceasefire"``.
    * ``"strength_a"``, ``"strength_b"`` – troop/equipment strength for
      each main side (numbers or structured payloads).
    * ``"casualties_a"``, ``"casualties_b"`` – numeric or textual
      casualty information.
    * ``"theater"`` – name of the theater/front within a wider war.
    * ``"campaign_name"`` – campaign or operation name.
    * ``"operation_code_name"`` – if distinct from the public name.
    * ``"front"``, ``"phase"`` – to situate this event within a larger
      conflict.
    * ``"objective"`` – primary military or political objective.

    Usage notes
    -----------
    * No additional dataclass fields are introduced beyond those in
      :class:`Event`; this frame exists to provide a stable
      ``frame_type`` and documented conventions.
    * Normalization code is expected to:
      * construct :class:`ConflictWarEventFrame` instances,
      * set ``event_type`` appropriately (e.g. ``"war"``, ``"battle"``),
      * populate participants and properties using the conventions above.
    * Renderers and planners can rely on ``frame_type ==
      "event.conflict-event"`` to select conflict-specific constructions
      (e.g. “X was a battle between A and B during Y …”).
    """

    # Canonical frame type key used for routing and schema identification.
    # Updated to match test expectation "event.conflict-event"
    frame_type: ClassVar[str] = "event.conflict-event"


__all__ = ["ConflictWarEventFrame"]
