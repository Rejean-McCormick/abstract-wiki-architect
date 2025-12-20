# app\core\domain\semantics\roles.py
# semantics\roles.py
"""
semantics/roles.py
==================

Canonical labels and helpers for semantic / syntactic roles.

This module centralizes the role names used across:

- semantic frames (e.g. BioFrame, EventFrame),
- constructions (ClauseInput.roles),
- discourse / information-structure annotations.

The goal is to:

- use short, stable, UPPERCASE codes internally (e.g. "SUBJ", "AGENT"),
- accept many human-friendly aliases ("subject", "agent", "theme", etc.),
- provide helpers to normalize and group roles.

Typical usage
-------------

    from semantics import roles as R

    role = R.canonical_role("subject")        # → "SUBJ"
    is_core = R.is_core_role(role)           # True

    normalized = R.normalize_roles({
        "subject": subj_entity,
        "object": obj_entity,
        "time":   time_span,
    })
    # normalized keys: "SUBJ", "OBJ", "TIME"

The rest of the system should ideally only see canonical labels; all
user-facing or external labels should be normalized via this module.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping


# ---------------------------------------------------------------------------
# Canonical role codes
# ---------------------------------------------------------------------------

# Core syntactic / semantic arguments
SUBJ = "SUBJ"  # syntactic subject (often maps to AGENT or EXPERIENCER)
OBJ = "OBJ"  # direct object (PATIENT/THEME)
IOBJ = "IOBJ"  # indirect object (RECIPIENT/BENEFICIARY)

AGENT = "AGENT"  # doer / initiator
PATIENT = "PATIENT"  # undergoer / affected participant
EXPERIENCER = "EXP"  # experiencer of a mental state
THEME = "THEME"  # moved/located entity (when distinct from PATIENT)
RECIPIENT = "RECIP"  # receiver in transfer events
BENEFICIARY = "BENEF"  # beneficiary of an action
INSTRUMENT = "INSTR"  # instrument / means

# Local / oblique roles
LOCATION = "LOC"
SOURCE = "SRC"
GOAL = "GOAL"
PATH = "PATH"
MANNER = "MANNER"
CAUSE = "CAUSE"
RESULT = "RESULT"
EXTENT = "EXTENT"
TIME = "TIME"

# Possession / attribution
POSSESSOR = "POSS"
POSSESSED = "POSS_OBJ"
ATTRIBUTE = "ATTR"  # property / attribute (e.g. profession, nationality)

# Comparative / scalar structure
COMPARANDUM = "COMP_BASE"  # entity being compared (X in "X is taller than Y")
STANDARD = "COMP_STD"  # standard of comparison (Y in "X is taller than Y")
DOMAIN = "COMP_DOMAIN"  # domain set ("in her field", "among physicists")

# Copular / predicative roles
COP_SUBJ = "COP_SUBJ"  # subject of copula (often same as SUBJ)
COP_PRED = "COP_PRED"  # predicate nominal/adjective

# Relative clauses
REL_HEAD = "REL_HEAD"  # head noun of the relative clause
REL_RESTRICTOR = "REL_RESTR"  # clause that restricts the head

# Information structure
TOPIC = "TOPIC"
FOCUS = "FOCUS"
BACKGROUND = "BKG"

# Discourse roles (for multi-sentence planning)
DISCOURSE_TOPIC = "DISC_TOPIC"
DISCOURSE_NEW = "DISC_NEW"
DISCOURSE_OLD = "DISC_OLD"


# ---------------------------------------------------------------------------
# Groupings for quick checks
# ---------------------------------------------------------------------------

CORE_ARGUMENT_ROLES = {
    SUBJ,
    OBJ,
    IOBJ,
    AGENT,
    PATIENT,
    EXPERIENCER,
    THEME,
    RECIPIENT,
}

OBLIQUE_ROLES = {
    LOCATION,
    SOURCE,
    GOAL,
    PATH,
    MANNER,
    INSTRUMENT,
    CAUSE,
    RESULT,
    EXTENT,
    TIME,
}

POSSESSION_ROLES = {
    POSSESSOR,
    POSSESSED,
}

INFORMATION_STRUCTURE_ROLES = {
    TOPIC,
    FOCUS,
    BACKGROUND,
    DISCOURSE_TOPIC,
    DISCOURSE_NEW,
    DISCOURSE_OLD,
}

COMPARATIVE_ROLES = {
    COMPARANDUM,
    STANDARD,
    DOMAIN,
}

COPULAR_ROLES = {
    COP_SUBJ,
    COP_PRED,
}

RELATIVE_ROLES = {
    REL_HEAD,
    REL_RESTRICTOR,
}

ALL_ROLES = (
    CORE_ARGUMENT_ROLES
    | OBLIQUE_ROLES
    | POSSESSION_ROLES
    | INFORMATION_STRUCTURE_ROLES
    | COMPARATIVE_ROLES
    | COPULAR_ROLES
    | RELATIVE_ROLES
)


# ---------------------------------------------------------------------------
# Aliases (input labels → canonical codes)
# ---------------------------------------------------------------------------

_ROLE_ALIASES: Dict[str, str] = {
    # Subjects / objects
    "subject": SUBJ,
    "subj": SUBJ,
    "s": SUBJ,
    "object": OBJ,
    "obj": OBJ,
    "o": OBJ,
    "iobj": IOBJ,
    "indirect_object": IOBJ,
    # Semantic arguments
    "agent": AGENT,
    "a": AGENT,
    "doer": AGENT,
    "patient": PATIENT,
    "p": PATIENT,
    "theme": THEME,
    "experiencer": EXPERIENCER,
    "exp": EXPERIENCER,
    "recipient": RECIPIENT,
    "beneficiary": BENEFICIARY,
    "benefactive": BENEFICIARY,
    "instrument": INSTRUMENT,
    "inst": INSTRUMENT,
    # Locatives / obliques
    "loc": LOCATION,
    "location": LOCATION,
    "place": LOCATION,
    "source": SOURCE,
    "src": SOURCE,
    "from": SOURCE,
    "goal": GOAL,
    "to": GOAL,
    "path": PATH,
    "manner": MANNER,
    "cause": CAUSE,
    "reason": CAUSE,
    "result": RESULT,
    "extent": EXTENT,
    "time": TIME,
    "temporal": TIME,
    # Possession / attribution
    "possessor": POSSESSOR,
    "owner": POSSESSOR,
    "possessed": POSSESSED,
    "possession": POSSESSED,
    "attribute": ATTRIBUTE,
    "property": ATTRIBUTE,
    "role": ATTRIBUTE,  # e.g. profession/nationality, often rendered as predicate
    # Comparative
    "comparandum": COMPARANDUM,
    "comp_base": COMPARANDUM,
    "standard": STANDARD,
    "comp_standard": STANDARD,
    "domain": DOMAIN,
    "comp_domain": DOMAIN,
    # Copular
    "cop_subj": COP_SUBJ,
    "cop_subject": COP_SUBJ,
    "cop_pred": COP_PRED,
    "cop_predicate": COP_PRED,
    # Relative
    "rel_head": REL_HEAD,
    "relative_head": REL_HEAD,
    "rel_restrictor": REL_RESTRICTOR,
    "relative_clause": REL_RESTRICTOR,
    # Information structure / discourse
    "topic": TOPIC,
    "focus": FOCUS,
    "background": BACKGROUND,
    "disc_topic": DISCOURSE_TOPIC,
    "discourse_topic": DISCOURSE_TOPIC,
    "disc_new": DISCOURSE_NEW,
    "disc_old": DISCOURSE_OLD,
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def canonical_role(label: str) -> str:
    """
    Map an arbitrary label (case-insensitive) to a canonical role code.

    Examples:
        canonical_role("subject")    -> "SUBJ"
        canonical_role("Agent")      -> "AGENT"
        canonical_role("time")       -> "TIME"

    If the label is not known, it falls back to UPPERCASE version of the input.
    This makes it safe to pass through user-defined labels while still
    benefiting from canonicalization where possible.
    """
    if not label:
        raise ValueError("Role label must be a non-empty string.")

    raw = label.strip()
    if not raw:
        raise ValueError("Role label must contain non-whitespace characters.")

    # If already a canonical code, keep it
    upper = raw.upper()
    if upper in ALL_ROLES:
        return upper

    # Try known aliases (case-insensitive)
    lower = raw.lower()
    if lower in _ROLE_ALIASES:
        return _ROLE_ALIASES[lower]

    # Fallback: just return the uppercased label
    return upper


def normalize_roles(
    roles: Mapping[str, Any],
    *,
    merge: bool = True,
) -> Dict[str, Any]:
    """
    Normalize role labels in a mapping to canonical codes.

    Args:
        roles:
            A mapping from (possibly messy) labels → values, e.g.:

                {
                    "subject": subj_entity,
                    "object": obj_entity,
                    "time":   time_span,
                }

        merge:
            If True (default), roles that normalize to the same canonical
            code are merged, with *later* entries overwriting earlier ones.
            If False, the last occurrence still wins, but this is just
            a reminder flag for callers.

    Returns:
        A new dict whose keys are canonical role codes, e.g.:

            {
                "SUBJ": subj_entity,
                "OBJ":  obj_entity,
                "TIME": time_span,
            }
    """
    normalized: Dict[str, Any] = {}
    for raw_label, value in roles.items():
        canonical = canonical_role(raw_label)
        if merge:
            normalized[canonical] = value
        else:
            # Behavior is the same (last wins), but the flag documents intent.
            normalized[canonical] = value
    return normalized


def is_core_role(label: str) -> bool:
    """
    Return True if the label (after normalization) is a core argument role.
    """
    return canonical_role(label) in CORE_ARGUMENT_ROLES


def is_oblique_role(label: str) -> bool:
    """
    Return True if the label (after normalization) is a local/oblique role.
    """
    return canonical_role(label) in OBLIQUE_ROLES


def is_possession_role(label: str) -> bool:
    """
    Return True if the label (after normalization) is a possession-related role.
    """
    return canonical_role(label) in POSSESSION_ROLES


def is_information_structure_role(label: str) -> bool:
    """
    Return True if the label (after normalization) is an information-structure role.
    """
    return canonical_role(label) in INFORMATION_STRUCTURE_ROLES


def is_comparative_role(label: str) -> bool:
    """
    Return True if the label (after normalization) is a comparative role.
    """
    return canonical_role(label) in COMPARATIVE_ROLES


def is_copular_role(label: str) -> bool:
    """
    Return True if the label (after normalization) is a copular role.
    """
    return canonical_role(label) in COPULAR_ROLES


def is_relative_role(label: str) -> bool:
    """
    Return True if the label (after normalization) is a relative-clause role.
    """
    return canonical_role(label) in RELATIVE_ROLES


def canonicalize_labels(labels: Iterable[str]) -> Dict[str, str]:
    """
    Convenience helper: given an iterable of labels, return a mapping
    from original label → canonical code.

    Example:
        canonicalize_labels(["subject", "object", "time"])
        # {"subject": "SUBJ", "object": "OBJ", "time": "TIME"}
    """
    return {label: canonical_role(label) for label in labels}


__all__ = [
    # Canonical codes
    "SUBJ",
    "OBJ",
    "IOBJ",
    "AGENT",
    "PATIENT",
    "EXPERIENCER",
    "THEME",
    "RECIPIENT",
    "BENEFICIARY",
    "INSTRUMENT",
    "LOCATION",
    "SOURCE",
    "GOAL",
    "PATH",
    "MANNER",
    "CAUSE",
    "RESULT",
    "EXTENT",
    "TIME",
    "POSSESSOR",
    "POSSESSED",
    "ATTRIBUTE",
    "COMPARANDUM",
    "STANDARD",
    "DOMAIN",
    "COP_SUBJ",
    "COP_PRED",
    "REL_HEAD",
    "REL_RESTRICTOR",
    "TOPIC",
    "FOCUS",
    "BACKGROUND",
    "DISCOURSE_TOPIC",
    "DISCOURSE_NEW",
    "DISCOURSE_OLD",
    # Groupings
    "CORE_ARGUMENT_ROLES",
    "OBLIQUE_ROLES",
    "POSSESSION_ROLES",
    "INFORMATION_STRUCTURE_ROLES",
    "COMPARATIVE_ROLES",
    "COPULAR_ROLES",
    "RELATIVE_ROLES",
    "ALL_ROLES",
    # Functions
    "canonical_role",
    "normalize_roles",
    "is_core_role",
    "is_oblique_role",
    "is_possession_role",
    "is_information_structure_role",
    "is_comparative_role",
    "is_copular_role",
    "is_relative_role",
    "canonicalize_labels",
]
