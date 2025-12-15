# semantics\relational\change_of_state_frame.py
# semantics/relational/change_of_state_frame.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from semantics.types import Entity, Event, TimeSpan


@dataclass
class ChangeOfStateFrame:
    """
    Change of state for a single subject entity.

    This relational frame captures transitions of an entity between states,
    optionally with a triggering event and temporal information.

    Typical examples:
        - "The town became a city in 1905."
        - "The institution was abolished in 1999."
        - "The company was renamed X in 2010."

    Fields
    ------

    subject:
        The entity undergoing the change (X in “X became Y”, “X was abolished”).
    change_type:
        High-level label for the type of change, e.g.
        "become", "abolish", "rename", "merge", "convert", "split".
        This is intentionally a free string so projects can normalize or
        subclass as needed.
    id:
        Optional stable identifier for this relational fact (for cross-references,
        provenance, etc.).
    old_state:
        Optional free-text label for the previous state, e.g. a type label
        ("town") or old name. Can be left None if unknown or not needed.
    new_state:
        Optional free-text label for the new state, e.g. a new type or name.
        For renaming, this would typically hold the new name.
    trigger_event:
        Optional Event that triggered the change, if you want to keep a richer
        representation (e.g. a specific law being passed, a merger event).
    trigger_description:
        Optional short free-text description of the trigger when a full Event
        is not available or would be overkill (e.g. "following a reform").
    time:
        Optional TimeSpan describing when the change took place (or the main
        year/date associated with it).
    certainty:
        Confidence score in [0.0, 1.0]. Defaults to 1.0 for asserted facts.
    source_id:
        Optional citation / source handle (e.g. reference key, Wikidata statement id).
    extra:
        Free-form metadata dictionary for callers to store auxiliary information.
    """

    # Core participants
    subject: Entity
    change_type: str

    # Identity / metadata
    id: Optional[str] = None

    # State labels
    old_state: Optional[str] = None
    new_state: Optional[str] = None

    # Triggers / causes
    trigger_event: Optional[Event] = None
    trigger_description: Optional[str] = None

    # Temporal + provenance
    time: Optional[TimeSpan] = None
    certainty: float = 1.0
    source_id: Optional[str] = None

    # Extension hook
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ChangeOfStateFrame"]
