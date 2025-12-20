# app\core\domain\semantics\common\quantity.py
# semantics\common\quantity.py
"""
semantics/common/quantity.py

Lightweight, language-independent abstractions for numeric quantities.

These types are meant to be reused across many frame families, in
particular:

- Quantitative measure frames (population, area, GDP, scores, etc.).
- Comparative / ranking frames (“bigger than…”, “second-largest…”).
- Any frame that needs to encode a number + unit + qualifier (“about”,
  “at least”, “no more than”) without committing to any surface form.

Design goals
------------

- **Pure semantics**: no string templates, no language-specific logic.
- **Low ceremony**: simple dataclasses, easy to construct from JSON /
  Wikidata-style payloads.
- **Flexible**: can represent point values, bounds, and simple intervals.
- **Safe defaults**: missing fields are treated as “unknown”, not 0.

Downstream code (normalization, frame builders, NLG) is expected to:

- Populate these structures from external sources.
- Decide how to *verbalize* qualifiers and units per language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, Union


# ---------------------------------------------------------------------------
# Basic numeric aliases
# ---------------------------------------------------------------------------

Number = Union[int, float]


# ---------------------------------------------------------------------------
# Core enums (as Literals)
# ---------------------------------------------------------------------------

QuantityKind = Literal[
    "count",  # plain counts: 5 people, 12 teams
    "measure",  # physical / economic measures: 3.5 km, 2 kg, 1.2e6 USD
    "percentage",  # 42 %
    "ratio",  # dimensionless or composite ratios
    "index",  # abstract indices: HDI, CPI, etc.
    "ordinal",  # 1st, 2nd, 3rd…
    "rank",  # position in a ranking: #1, #2…
    "other",  # fallback for anything not fitting above
]


QuantityQualifier = Literal[
    "exact",  # exactly 10 000
    "approximate",  # about / roughly / circa 10 000
    "at_least",  # ≥ 10 000
    "at_most",  # ≤ 10 000
    "unknown",  # some number exists but we do not know how precise
]


# ---------------------------------------------------------------------------
# Unit representation
# ---------------------------------------------------------------------------


@dataclass
class Unit:
    """
    Representation of a measurement unit.

    This is intentionally minimal and “code-first”: the main field is
    `code`, which can be anything but is expected to be stable across
    the system (e.g. "person", "km2", "USD", "percent").

    Attributes
    ----------
    code:
        Canonical code for the unit, e.g. "km", "km2", "USD", "person",
        "percent". For purely dimensionless quantities, you can use
        "1", "unitless", or an empty string.

    name:
        Optional human-readable name (English or UI language), e.g.
        "kilometre", "square kilometre", "US dollar".

        This is *not* used in NLG directly; constructions should map
        `code` to language-specific lexemes.

    system:
        Optional system label, e.g. "SI", "USD", "EUR", "custom".

    per:
        Optional “per” component for rate-like units, e.g.:

        - code="person", per="km2"  →  persons per square kilometre
        - code="USD", per="year"    →  USD per year

        This is deliberately a free-form string; more complex
        factorization (numerator vs denominator units) can be added
        later if needed.
    """

    code: str
    name: Optional[str] = None
    system: Optional[str] = None
    per: Optional[str] = None

    def __post_init__(self) -> None:
        # Normalize trivial whitespace; keep everything else as given.
        self.code = (self.code or "").strip()
        if self.name is not None:
            self.name = self.name.strip() or None
        if self.system is not None:
            self.system = self.system.strip() or None
        if self.per is not None:
            self.per = self.per.strip() or None

    # ------------------------------------------------------------------ #
    # Convenience predicates
    # ------------------------------------------------------------------ #

    def is_dimensionless(self) -> bool:
        """
        Return True if this unit has no meaningful physical dimension.

        We treat codes like "", "1", "unitless", "dimensionless" as
        dimensionless for convenience.
        """
        code = self.code.lower()
        if not code:
            return True
        return code in {"1", "unitless", "dimensionless"}

    def compact(self) -> str:
        """
        Return a compact, language-neutral string representation.

        Examples
        --------
        - Unit(code="km2")                → "km2"
        - Unit(code="USD", per="year")    → "USD/year"
        - Unit(code="person", per="km2")  → "person/km2"
        """
        if self.per:
            return f"{self.code}/{self.per}"
        return self.code


# ---------------------------------------------------------------------------
# Quantity representation
# ---------------------------------------------------------------------------


@dataclass
class Quantity:
    """
    Numeric quantity + unit + qualifier.

    This is the main “semantic” object for numeric information. It can
    represent everything from:

    - point values (“population 10 000 (as of 2020)”)
    - approximate values (“about 3 km”)
    - lower/upper bounds (“at least 10”, “no more than 5”)
    - simple closed intervals (“between 3 and 5 km”)

    Attributes
    ----------
    kind:
        Coarse semantic type of the quantity. This is *not* the unit:
        you can have kind="count" with unit=Unit("person"), or
        kind="percentage" with unit=Unit("percent").

    value:
        Preferred or central numeric value. For simple point values this
        is the only numeric field used.

        For intervals/bounds you may also fill `min_value` / `max_value`
        and keep `value` as either None or a representative central
        value (e.g. midpoint), depending on your downstream needs.

    unit:
        Optional Unit object. May be None for dimensionless quantities
        (indices, some ratios, ordinal ranks, etc.).

    qualifier:
        High-level qualifier describing how to interpret the numeric
        value:

        - "exact"       → treat as an exact or rounded figure.
        - "approximate" → “about”, “roughly”, “around”.
        - "at_least"    → lower-bound constraint.
        - "at_most"     → upper-bound constraint.
        - "unknown"     → some numeric value exists but precision is not
                          clearly specified.

        Bound qualifiers typically go together with either `min_value`
        or `max_value`.

    min_value / max_value:
        Optional lower/upper bounds for the quantity. If both are set
        and differ, this represents a closed interval.

        Examples
        --------
        - min_value=10, max_value=None, qualifier="at_least"
        - min_value=None, max_value=5,  qualifier="at_most"
        - min_value=3,   max_value=5,   qualifier="exact" (interval)

    as_of:
        Optional temporal anchor for the quantity, typically a date or
        year. The *type* is intentionally loose (Any) so that callers
        can use:

        - a datetime.date / datetime.datetime,
        - a semantics.types.TimeSpan,
        - or a simple string like "2020-01-01" / "2020".

        Downstream code is responsible for interpreting this.

    scope:
        Optional scope or denominator as a free-form string, e.g.:

        - "per capita"
        - "per 100 000 inhabitants"
        - "within city limits"

        Use this for semantic scoping that is not easily captured by
        the `unit.per` field alone.

    raw:
        Optional raw string from the source (e.g. Wikidata value with
        unit or qualifiers) for debugging or fallbacks.

    meta:
        Arbitrary extra metadata, for things that should travel with the
        quantity but are not part of the core schema (e.g. source IDs,
        confidence scores, provenance).
    """

    kind: QuantityKind = "measure"
    value: Optional[Number] = None
    unit: Optional[Unit] = None
    qualifier: QuantityQualifier = "exact"

    min_value: Optional[Number] = None
    max_value: Optional[Number] = None

    as_of: Optional[Any] = None
    scope: Optional[str] = None

    raw: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Convenience predicates
    # ------------------------------------------------------------------ #

    def is_missing(self) -> bool:
        """
        Return True if there is no usable numeric information.

        This checks that:
        - `value` is None, and
        - both `min_value` and `max_value` are None.
        """
        return self.value is None and self.min_value is None and self.max_value is None

    def is_interval(self) -> bool:
        """
        Return True if the quantity encodes a non-degenerate interval.

        A “non-degenerate interval” here means both bounds are present
        and differ numerically.
        """
        if self.min_value is None or self.max_value is None:
            return False
        return self.min_value != self.max_value

    def has_lower_bound(self) -> bool:
        """
        Return True if a lower bound is present.
        """
        return self.min_value is not None

    def has_upper_bound(self) -> bool:
        """
        Return True if an upper bound is present.
        """
        return self.max_value is not None

    # ------------------------------------------------------------------ #
    # Convenience constructors
    # ------------------------------------------------------------------ #

    @classmethod
    def point(
        cls,
        value: Number,
        unit: Optional[Unit] = None,
        *,
        kind: QuantityKind = "measure",
        qualifier: QuantityQualifier = "exact",
        as_of: Optional[Any] = None,
        scope: Optional[str] = None,
        raw: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "Quantity":
        """
        Construct a simple point-valued quantity.

        This is a convenience for the common case where there is a
        single numeric value (no explicit bounds).
        """
        return cls(
            kind=kind,
            value=value,
            unit=unit,
            qualifier=qualifier,
            min_value=None,
            max_value=None,
            as_of=as_of,
            scope=scope,
            raw=raw,
            meta=dict(meta or {}),
        )

    @classmethod
    def bounded(
        cls,
        *,
        min_value: Optional[Number] = None,
        max_value: Optional[Number] = None,
        unit: Optional[Unit] = None,
        kind: QuantityKind = "measure",
        qualifier: QuantityQualifier = "exact",
        as_of: Optional[Any] = None,
        scope: Optional[str] = None,
        raw: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "Quantity":
        """
        Construct a quantity with explicit lower / upper bounds.

        The central `value` field is left as None; callers may choose to
        fill it later (e.g. with the midpoint) if their use case
        benefits from having a single representative number.
        """
        return cls(
            kind=kind,
            value=None,
            unit=unit,
            qualifier=qualifier,
            min_value=min_value,
            max_value=max_value,
            as_of=as_of,
            scope=scope,
            raw=raw,
            meta=dict(meta or {}),
        )


__all__ = [
    "Number",
    "QuantityKind",
    "QuantityQualifier",
    "Unit",
    "Quantity",
]
