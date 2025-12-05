from __future__ import annotations

from typing import Protocol

from semantics.types import BioFrame, Event

# Alias Event to EventFrame to match the public API expectations
EventFrame = Event


class Frame(Protocol):
    frame_type: str


__all__ = ["Frame", "BioFrame", "EventFrame", "Event"]
