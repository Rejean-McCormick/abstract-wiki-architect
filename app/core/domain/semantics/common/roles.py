# semantics\common\roles.py
"""
semantics/common/roles.py
-------------------------

Utilities for working with semantic role labels used in events and frames.

This module provides:

    * A small inventory of canonical role labels (AGENT, PATIENT, ...).
    * A mapping of common aliases and project-specific labels onto those
      canonical roles.
    * Helper functions for normalizing role labels and iterating over
      participants in a stable, human-readable order.

The goal is to keep event participant role handling consistent across:

    * raw AbstractWiki / Wikidata style input,
    * internal `Event.participants` dictionaries,
    * higher-level frame families (e.g. biography, conflict, election).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from semantics.types import Entity, Event


# ---------------------------------------------------------------------------
# Canonical role labels
# ---------------------------------------------------------------------------

# Core semantic roles
AGENT: str = "agent"
PATIENT: str = "patient"
THEME: str = "theme"
EXPERIENCER: str = "experiencer"
STIMULUS: str = "stimulus"
RECIPIENT: str = "recipient"
BENEFICIARY: str = "beneficiary"
INSTRUMENT: str = "instrument"

# Locative / directional roles
LOCATION: str = "location"
SOURCE: str = "source"
GOAL: str = "goal"
PATH: str = "path"

# Discourse / relational roles
TOPIC: str = "topic"
CO_AGENT: str = "co-agent"
CO_PATIENT: str = "co-patient"
CO_THEME: str = "co-theme"

# Syntactic-ish convenience roles (often appear in input)
SUBJECT: str = "subject"
OBJECT: str = "object"
OBLIQUE: str = "oblique"

# A small, generic default role when nothing better is available
PARTICIPANT: str = "participant"


# Ordered list of canonical roles in a rough “importance” order.
_CANONICAL_ROLE_ORDER: List[str] = [
    SUBJECT,
    AGENT,
    CO_AGENT,
    PATIENT,
    THEME,
    CO_PATIENT,
    CO_THEME,
    RECIPIENT,
    BENEFICIARY,
    TOPIC,
    INSTRUMENT,
    LOCATION,
    SOURCE,
    GOAL,
    PATH,
    OBJECT,
    OBLIQUE,
    PARTICIPANT,
]


# Map *input* labels (possibly noisy or project-specific) to normalized
# internal labels.
_ROLE_ALIASES: Dict[str, str] = {
    # subject / agent-like
    "subj": SUBJECT,
    "subject": SUBJECT,
    "agent": AGENT,
    "arg0": AGENT,
    "a0": AGENT,
    "actor": AGENT,
    "doer": AGENT,
    "coagent": CO_AGENT,
    "co-agent": CO_AGENT,
    # object / patient / theme-like
    "obj": OBJECT,
    "object": OBJECT,
    "patient": PATIENT,
    "theme": THEME,
    "arg1": PATIENT,
    "a1": PATIENT,
    "arg2": THEME,
    "a2": THEME,
    "cotheme": CO_THEME,
    "co-theme": CO_THEME,
    "copatient": CO_PATIENT,
    "co-patient": CO_PATIENT,
    # recipient / beneficiary
    "recipient": RECIPIENT,
    "beneficiary": BENEFICIARY,
    "benefactor": BENEFICIARY,
    # instrument
    "instrument": INSTRUMENT,
    "instr": INSTRUMENT,
    # locations / directions
    "loc": LOCATION,
    "location": LOCATION,
    "place": LOCATION,
    "source": SOURCE,
    "from": SOURCE,
    "origin": SOURCE,
    "goal": GOAL,
    "to": GOAL,
    "destination": GOAL,
    "path": PATH,
    # discourse-ish
    "topic": TOPIC,
    "about": TOPIC,
    # generic participant
    "participant": PARTICIPANT,
    "arg": PARTICIPANT,
    "argx": PARTICIPANT,
    "argument": PARTICIPANT,
    "other": PARTICIPANT,
    # syntactic-ish
    "obl": OBLIQUE,
    "oblique": OBLIQUE,
}


# Map normalized labels to *canonical semantic roles* where we want a
# smaller inventory for realization decisions.
_CANONICAL_SEMANTIC_ROLES: Dict[str, str] = {
    SUBJECT: AGENT,
    AGENT: AGENT,
    CO_AGENT: AGENT,
    OBJECT: PATIENT,
    PATIENT: PATIENT,
    THEME: PATIENT,
    CO_PATIENT: PATIENT,
    CO_THEME: PATIENT,
    RECIPIENT: RECIPIENT,
    BENEFICIARY: BENEFICIARY,
    INSTRUMENT: INSTRUMENT,
    LOCATION: LOCATION,
    SOURCE: SOURCE,
    GOAL: GOAL,
    PATH: PATH,
    TOPIC: TOPIC,
    PARTICIPANT: PARTICIPANT,
    OBLIQUE: OBLIQUE,
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParticipantRole:
    """
    Small helper structure combining a role label with an entity.

    This is mainly for convenience when iterating over
    `Event.participants` in a stable, ordered fashion.
    """

    role: str
    entity: Entity


def normalize_role_label(label: str) -> str:
    """
    Normalize a raw role label into a consistent internal label.

    Steps:
        * lower-case and strip whitespace
        * look up in `_ROLE_ALIASES`
        * if not found, return the cleaned label as-is

    Examples:
        >>> normalize_role_label("Subj")
        'subject'
        >>> normalize_role_label("ARG0")
        'agent'
    """
    cleaned = label.strip().lower()
    if not cleaned:
        return PARTICIPANT
    return _ROLE_ALIASES.get(cleaned, cleaned)


def canonical_semantic_role(label: str) -> str:
    """
    Map a (possibly noisy) role label to a coarse canonical semantic role.

    This collapses syntactic-ish labels like "subject"/"object"
    into AGENT/PATIENT, and leaves unknown labels as-is.

    Examples:
        >>> canonical_semantic_role("subject")
        'agent'
        >>> canonical_semantic_role("object")
        'patient'
    """
    normalized = normalize_role_label(label)
    return _CANONICAL_SEMANTIC_ROLES.get(normalized, normalized)


def order_roles_for_realization(
    roles: Sequence[str],
) -> List[str]:
    """
    Return a new list of role labels ordered by importance for realization.

    - Known roles are sorted by `_CANONICAL_ROLE_ORDER`.
    - Unknown roles are kept at the end, in original order.

    This is useful for deciding which participant becomes the syntactic
    subject, object, etc., when generating a clause.
    """
    # Stable index for known roles
    order_index: Dict[str, int] = {r: i for i, r in enumerate(_CANONICAL_ROLE_ORDER)}

    def sort_key(role: str) -> tuple[int, int]:
        normalized = normalize_role_label(role)
        # Known roles get a small index; unknown roles get a big one.
        base = order_index.get(normalized, len(_CANONICAL_ROLE_ORDER))
        # Preserve original order among roles with same base index.
        return (base, roles.index(role))

    return sorted(roles, key=sort_key)


def iter_participants(
    event: Event,
    *,
    core_only: bool = False,
) -> Iterable[ParticipantRole]:
    """
    Iterate over an event's participants in a stable, importance-aware order.

    Args:
        event:
            The Event whose `participants` we want to traverse.
        core_only:
            If True, only yield core argument roles (subject/agent,
            patient/theme, recipient/beneficiary). If False, include all.

    Yields:
        ParticipantRole(role=<normalized-role>, entity=<Entity>)

    Note:
        - Role labels are normalized via `normalize_role_label`.
        - Ordering is determined by `order_roles_for_realization`.
    """
    if not event.participants:
        return []

    # Normalize roles and keep mapping
    normalized_to_entity: Dict[str, Entity] = {}
    for raw_role, ent in event.participants.items():
        norm = normalize_role_label(raw_role)
        normalized_to_entity[norm] = ent

    roles: List[str] = list(normalized_to_entity.keys())
    ordered_roles = order_roles_for_realization(roles)

    if core_only:
        core_set = {
            SUBJECT,
            AGENT,
            CO_AGENT,
            PATIENT,
            THEME,
            CO_PATIENT,
            CO_THEME,
            RECIPIENT,
            BENEFICIARY,
        }
        ordered_roles = [r for r in ordered_roles if r in core_set]

    for r in ordered_roles:
        yield ParticipantRole(role=r, entity=normalized_to_entity[r])


def get_main_agent(event: Event) -> Optional[Entity]:
    """
    Heuristic: return the entity to treat as the main *agent* of an event.

    Preference order:
        subject > agent > co-agent > (fall back to any participant)
    """
    if not event.participants:
        return None

    # Precompute normalized map
    normalized: Dict[str, Entity] = {}
    for raw_role, ent in event.participants.items():
        normalized[normalize_role_label(raw_role)] = ent

    for candidate_role in (SUBJECT, AGENT, CO_AGENT):
        if candidate_role in normalized:
            return normalized[candidate_role]

    # Fallback: first participant in ordered list
    for pr in iter_participants(event):
        return pr.entity

    return None


def get_main_patient(event: Event) -> Optional[Entity]:
    """
    Heuristic: return the entity to treat as the main *patient/theme*.

    Preference order:
        object > patient > theme > co-patient > co-theme > (fallback).
    """
    if not event.participants:
        return None

    normalized: Dict[str, Entity] = {}
    for raw_role, ent in event.participants.items():
        normalized[normalize_role_label(raw_role)] = ent

    for candidate_role in (OBJECT, PATIENT, THEME, CO_PATIENT, CO_THEME):
        if candidate_role in normalized:
            return normalized[candidate_role]

    # Fallback: second participant if available
    ordered = list(iter_participants(event))
    if len(ordered) >= 2:
        return ordered[1].entity

    return None


__all__ = [
    "AGENT",
    "PATIENT",
    "THEME",
    "EXPERIENCER",
    "STIMULUS",
    "RECIPIENT",
    "BENEFICIARY",
    "INSTRUMENT",
    "LOCATION",
    "SOURCE",
    "GOAL",
    "PATH",
    "TOPIC",
    "CO_AGENT",
    "CO_PATIENT",
    "CO_THEME",
    "SUBJECT",
    "OBJECT",
    "OBLIQUE",
    "PARTICIPANT",
    "ParticipantRole",
    "normalize_role_label",
    "canonical_semantic_role",
    "order_roles_for_realization",
    "iter_participants",
    "get_main_agent",
    "get_main_patient",
]
