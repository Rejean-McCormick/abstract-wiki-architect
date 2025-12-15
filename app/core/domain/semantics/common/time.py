# semantics\common\time.py
"""
semantics.common.time
=====================

Helper utilities for working with :class:`TimeSpan` objects.

The core `TimeSpan` dataclass lives in :mod:`semantics.types` and is kept
intentionally simple:

    - `start_year`, `end_year`
    - optional month/day for each endpoint
    - `approximate` flag
    - `extra` metadata

This module provides:

    - Small normalization helpers (parse years from loose values).
    - Convenience constructors for common patterns (lifespans, single-year
      spans, generic intervals).
    - Introspection helpers (is this a point vs. an interval?).
    - A compact debug/diagnostic string representation.

The goal is to keep all *time-shaping* logic in one place so that bridges
and normalizers can reuse it.
"""

from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any, Dict, Optional, Tuple

from semantics.types import TimeSpan

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Match a (possibly signed) year-like integer such as "1867" or "-42".
_YEAR_RE = re.compile(r"(-?\d{1,4})")

# Markers that typically signal an approximate year.
_CIRCA_MARKERS = (
    "c.",
    "ca.",
    "circa",
    "~",
    "≈",
    "about",
    "around",
)


# ---------------------------------------------------------------------------
# Parsing / normalization
# ---------------------------------------------------------------------------


def parse_year(value: Any) -> Tuple[Optional[int], bool]:
    """
    Parse a “year-like” value into an integer year and an approximate flag.

    This is intentionally forgiving and meant for bridge / normalization code.

    Examples
    --------
    >>> parse_year(1867)
    (1867, False)
    >>> parse_year("1867")
    (1867, False)
    >>> parse_year("c. 1867")
    (1867, True)
    >>> parse_year("about 1900?")
    (1900, True)
    >>> parse_year(None)
    (None, False)

    Parameters
    ----------
    value:
        An int, float, string, or other object. Strings may contain “circa”
        markers (e.g. "c. 1867", "circa 1867", "~1867", "1867?").

    Returns
    -------
    (year, approximate):
        `year` is an int if parsing succeeded, otherwise None.
        `approximate` is True if the input looked approximate (circa markers,
        trailing "?"), otherwise False. If `year` is None, `approximate` will
        always be False.
    """
    if value is None:
        return None, False

    # Fast path for integers
    if isinstance(value, int):
        return value, False

    # Floats that are integral
    if isinstance(value, float) and value.is_integer():
        return int(value), False

    # Strings and everything else: convert to str, then parse
    text = str(value).strip()
    if not text:
        return None, False

    lowered = text.lower()

    approx = False
    for marker in _CIRCA_MARKERS:
        if marker in lowered:
            approx = True
            break

    # Heuristic: trailing '?' often means "uncertain"
    if lowered.endswith("?"):
        approx = True

    match = _YEAR_RE.search(lowered)
    if not match:
        return None, False

    try:
        year = int(match.group(1))
    except ValueError:
        return None, False

    return year, approx


def normalize_year(value: Any) -> Optional[int]:
    """
    Lightweight convenience wrapper around :func:`parse_year`.

    Returns only the parsed year (or None), ignoring the approximate flag.
    """
    year, _ = parse_year(value)
    return year


# ---------------------------------------------------------------------------
# TimeSpan constructors
# ---------------------------------------------------------------------------


def make_timespan(
    *,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    start_month: Optional[int] = None,
    start_day: Optional[int] = None,
    end_month: Optional[int] = None,
    end_day: Optional[int] = None,
    approximate: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> TimeSpan:
    """
    Generic `TimeSpan` constructor with sensible defaults.

    This is essentially a thin wrapper that ensures we always pass a dict
    for `extra` and keeps the call sites a bit more readable.
    """
    return TimeSpan(
        start_year=start_year,
        end_year=end_year,
        start_month=start_month,
        start_day=start_day,
        end_month=end_month,
        end_day=end_day,
        approximate=approximate,
        extra={} if extra is None else dict(extra),
    )


def single_year_span(
    year: Any,
    *,
    approximate: Optional[bool] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[TimeSpan]:
    """
    Build a `TimeSpan` representing a single (possibly approximate) year.

    Parameters
    ----------
    year:
        Anything accepted by :func:`parse_year`.
    approximate:
        If provided, overrides the approximate flag inferred by parsing.
    extra:
        Optional extra metadata for the TimeSpan.

    Returns
    -------
    TimeSpan | None
        A span with `start_year` set and all other fields left as default,
        or None if no year could be parsed.
    """
    parsed_year, approx_flag = parse_year(year)
    if parsed_year is None:
        return None

    if approximate is not None:
        approx_flag = approximate

    return make_timespan(
        start_year=parsed_year,
        approximate=approx_flag,
        extra=extra,
    )


def lifespan_from_years(
    birth: Any,
    death: Any | None,
    *,
    allow_partial: bool = True,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[TimeSpan]:
    """
    Build a `TimeSpan` representing a lifespan from birth / death years.

    This is mostly a convenience for biography-style uses.

    Parameters
    ----------
    birth:
        Year-like value for birth.
    death:
        Year-like value for death (may be None / missing).
    allow_partial:
        If True (default), returns a TimeSpan even when only one endpoint
        is known. If False and one endpoint is missing, returns None.
    extra:
        Optional extra metadata for the TimeSpan.

    Returns
    -------
    TimeSpan | None
    """
    birth_year, approx_birth = parse_year(birth)
    death_year, approx_death = parse_year(death) if death is not None else (None, False)

    if birth_year is None and death_year is None:
        return None

    if not allow_partial and (birth_year is None or death_year is None):
        return None

    approximate = approx_birth or approx_death

    # When only one endpoint is known, represent it as a point span.
    if birth_year is not None and death_year is None:
        return make_timespan(
            start_year=birth_year,
            approximate=approximate,
            extra=extra,
        )
    if birth_year is None and death_year is not None:
        return make_timespan(
            start_year=death_year,
            approximate=approximate,
            extra=extra,
        )

    # Both endpoints known
    return make_timespan(
        start_year=birth_year,
        end_year=death_year,
        approximate=approximate,
        extra=extra,
    )


def span_from_iso_date(
    date_str: str,
    *,
    approximate: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[TimeSpan]:
    """
    Construct a `TimeSpan` from a simple ISO-like date string.

    Supported input shapes (very intentionally limited):

        - "YYYY"
        - "YYYY-MM"
        - "YYYY-MM-DD"

    If the string cannot be parsed, returns None.

    Parameters
    ----------
    date_str:
        ISO-like date string.
    approximate:
        Explicit approximate flag (ignored for invalid input).
    extra:
        Optional extra metadata.

    Returns
    -------
    TimeSpan | None
    """
    text = (date_str or "").strip()
    if not text:
        return None

    parts = text.split("-")
    try:
        year = int(parts[0])
    except (ValueError, IndexError):
        return None

    month = day = None
    if len(parts) >= 2:
        try:
            month = int(parts[1])
        except ValueError:
            month = None
    if len(parts) == 3:
        try:
            day = int(parts[2])
        except ValueError:
            day = None

    return make_timespan(
        start_year=year,
        start_month=month,
        start_day=day,
        approximate=approximate,
        extra=extra,
    )


# ---------------------------------------------------------------------------
# Introspection / formatting
# ---------------------------------------------------------------------------


def is_point(span: TimeSpan) -> bool:
    """
    Return True if the TimeSpan represents a single point (year / date)
    rather than an interval.

    Heuristics
    ----------
    - `start_year` is not None, and
    - `end_year` is None or equal to `start_year`, and
    - `end_month` / `end_day` are unset.
    """
    if span.start_year is None:
        return False

    if span.end_year not in (None, span.start_year):
        return False

    if span.end_month is not None or span.end_day is not None:
        return False

    return True


def has_end(span: TimeSpan) -> bool:
    """
    Return True if the TimeSpan has a meaningful end (end_year not None).
    """
    return span.end_year is not None


def timespan_debug_string(span: Optional[TimeSpan]) -> str:
    """
    Return a compact, human-readable representation of a TimeSpan.

    This is primarily meant for logging, debugging, and tests; it is *not*
    intended as a localized user-facing string.

    Examples
    --------
    - TimeSpan(start_year=1867)                -> "1867"
    - TimeSpan(1867, 1934)                     -> "1867–1934"
    - TimeSpan(1867, start_month=11, ...)      -> "1867-11-??"
    - approximate=True                         -> prefix "~" if not already
    """
    if span is None:
        return "∅"

    # Base year parts
    def _date_part(y: Optional[int], m: Optional[int], d: Optional[int]) -> str:
        if y is None:
            return "?"
        if m is None and d is None:
            return str(y)
        mm = f"{m:02d}" if m is not None else "??"
        dd = f"{d:02d}" if d is not None else "??"
        return f"{y}-{mm}-{dd}"

    start = _date_part(span.start_year, span.start_month, span.start_day)
    end = (
        _date_part(span.end_year, span.end_month, span.end_day)
        if span.end_year is not None
        else ""
    )

    core = start if not end or start == end else f"{start}–{end}"
    if span.approximate and not core.startswith("~"):
        core = "~" + core
    return core


def timespan_to_dict(span: Optional[TimeSpan]) -> Dict[str, Any]:
    """
    Convert a TimeSpan into a plain dict for logging or JSON debugging.

    This is a shallow wrapper around :func:`dataclasses.asdict` that also
    gracefully handles `None`.
    """
    if span is None:
        return {}
    return asdict(span)


__all__ = [
    "parse_year",
    "normalize_year",
    "make_timespan",
    "single_year_span",
    "lifespan_from_years",
    "span_from_iso_date",
    "is_point",
    "has_end",
    "timespan_debug_string",
    "timespan_to_dict",
]
