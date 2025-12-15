# semantics\event\legal_case_event_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List

from semantics.types import Entity, Event, TimeSpan


__all__ = ["LegalCaseEventFrame"]


@dataclass
class LegalCaseEventFrame:
    """
    Semantic frame for a legal / judicial case or proceeding.

    This frame is designed to capture the core encyclopedic facts about a single
    legal case (trial, appeal, landmark decision, etc.) in a language-agnostic
    way. It builds on the generic `Event` type from `semantics.types` and adds
    fields that are commonly needed for Wikipedia-style summaries.

    The frame is intentionally simple:

    * All text-like fields (e.g. `issues`, `verdict_summary`) are neutral labels,
      not surface sentences.
    * All entities (court, parties, jurisdiction) are represented as `Entity`
      instances.
    * More specialized or project-specific information should go into
      `attributes` or `extra`.

    Recommended usage:

    * `main_event` carries the core semantic event for the case with
      `event.event_type` typically set to something like `"legal_case"`,
      `"trial"`, or `"appeal"`.
    * `court` and `jurisdiction` identify the deciding body and its scope.
    * `parties` groups participants by role (e.g. "plaintiff", "defendant",
      "appellant", "respondent").
    * `issues` lists the main legal questions or topics at stake.
    * `verdict_date` can refine the time of the decision if needed; otherwise,
      use `main_event.time`.
    """

    # Stable frame identifier for routing / dispatch
    # marked as ClassVar to exclude from __init__ order
    frame_type: ClassVar[str] = "event.legal_case"

    # Core event semantics
    main_event: Event

    # Identification
    case_id: str | None = None  # e.g. local ID or citation key
    case_name: str | None = None  # neutral label, e.g. "Brown v. Board of Education"

    # Institutions and scope
    court: Entity | None = None  # deciding court/tribunal
    jurisdiction: Entity | None = None  # jurisdiction or country/region

    # Parties and roles in a case
    #
    # Example structure:
    #   {
    #       "plaintiff": [Entity(...), ...],
    #       "defendant": [Entity(...), ...],
    #       "appellant": [Entity(...), ...],
    #       "respondent": [Entity(...), ...],
    #   }
    parties: Dict[str, List[Entity]] = field(default_factory=dict)

    # Main legal issues / questions (neutral labels, not sentences)
    issues: List[str] = field(default_factory=list)

    # Outcome and consequences
    verdict_summary: str | None = None  # short neutral label for the outcome
    verdict_date: TimeSpan | None = None
    sentence_summary: str | None = None  # for criminal cases, if applicable
    precedent_summary: str | None = None  # how the case is viewed as precedent

    # Optional references / citations in neutral form (e.g. reporter citations)
    citations: List[str] = field(default_factory=list)

    # Generic extension points
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
