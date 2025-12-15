# lexicon\schema.py
"""
lexicon/schema.py
=================

Lightweight schema and validation helpers for lexicon JSON files.

The goal here is *not* to enforce a huge, fragile specification, but to:

- Ensure basic structural sanity:
  - Top-level object is a dict.
  - Known sections (entries, lemmas, professions, etc.) are dicts.
  - Lemma keys are strings.
  - Each entry has at least a `pos` or equivalent hint where expected.
- Track a simple schema version for future migrations.

We deliberately avoid depending on external libraries like `jsonschema`:
validation is done with straightforward Python checks so it can run
anywhere, including Wikifunctions-like environments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional


SCHEMA_VERSION: int = 1


@dataclass
class SchemaIssue:
    """
    A single validation issue detected in a lexicon file.

    Fields:
        path:
            String describing where the issue occurred, e.g.
            "entries.physicist" or "meta.language".
        message:
            Human-readable description of the problem.
        level:
            "error" or "warning". Errors should generally fail CI / QA;
            warnings are informational.
    """

    path: str
    message: str
    level: str = "error"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_top_level_dict(data: Any) -> List[SchemaIssue]:
    if not isinstance(data, dict):
        return [
            SchemaIssue(
                path="",
                message="Top-level lexicon JSON must be an object (dict).",
                level="error",
            )
        ]
    return []


def _validate_meta(lang_code: str, data: Dict[str, Any]) -> List[SchemaIssue]:
    issues: List[SchemaIssue] = []
    meta_raw = data.get("meta") or data.get("_meta")

    if meta_raw is None:
        issues.append(
            SchemaIssue(
                path="meta",
                message="Missing 'meta'/_meta section; consider adding basic metadata.",
                level="warning",
            )
        )
        return issues

    if not isinstance(meta_raw, dict):
        issues.append(
            SchemaIssue(
                path="meta",
                message="'meta'/_meta must be an object (dict).",
                level="error",
            )
        )
        return issues

    # language sanity
    lang = meta_raw.get("language")
    if lang is None:
        issues.append(
            SchemaIssue(
                path="meta.language",
                message="Missing 'language' field in meta; should match lexicon language code.",
                level="warning",
            )
        )
    elif not isinstance(lang, str):
        issues.append(
            SchemaIssue(
                path="meta.language",
                message="'language' field in meta must be a string.",
                level="error",
            )
        )
    elif lang_code and lang_code != lang:
        issues.append(
            SchemaIssue(
                path="meta.language",
                message=(
                    f"Language mismatch: meta.language={lang!r}, "
                    f"expected {lang_code!r}."
                ),
                level="warning",
            )
        )

    # schema version
    schema_ver = meta_raw.get("schema_version")
    if schema_ver is None:
        issues.append(
            SchemaIssue(
                path="meta.schema_version",
                message=(
                    "Missing 'schema_version' in meta; "
                    f"current internal schema version is {SCHEMA_VERSION}."
                ),
                level="warning",
            )
        )
    elif not isinstance(schema_ver, int):
        issues.append(
            SchemaIssue(
                path="meta.schema_version",
                message="'schema_version' must be an integer.",
                level="error",
            )
        )
    elif schema_ver != SCHEMA_VERSION:
        issues.append(
            SchemaIssue(
                path="meta.schema_version",
                message=(
                    f"schema_version={schema_ver} does not match "
                    f"current internal schema version {SCHEMA_VERSION}."
                ),
                level="warning",
            )
        )

    return issues


def _validate_lemma_section(
    section_name: str,
    section: Any,
    *,
    require_pos: bool = False,
) -> List[SchemaIssue]:
    """
    Validate a lemma-bearing section such as:
        entries, lemmas, professions, nationalities, titles, honours.

    We assert:
        - section is a dict
        - keys (lemmas) are strings
        - values are dict-like entries
        - optional POS sanity if require_pos=True
    """
    issues: List[SchemaIssue] = []

    if not isinstance(section, Mapping):
        issues.append(
            SchemaIssue(
                path=section_name,
                message=f"Section '{section_name}' must be an object (dict) mapping lemmas to entries.",
                level="error",
            )
        )
        return issues

    for lemma, entry in section.items():
        path_prefix = f"{section_name}.{lemma!r}"

        if not isinstance(lemma, str):
            issues.append(
                SchemaIssue(
                    path=section_name,
                    message="Lemma keys must be strings.",
                    level="error",
                )
            )
            # Skip further checks for this key
            continue

        if not isinstance(entry, Mapping):
            issues.append(
                SchemaIssue(
                    path=path_prefix,
                    message="Entry value must be an object (dict).",
                    level="error",
                )
            )
            continue

        if require_pos:
            pos = entry.get("pos")
            if pos is None:
                issues.append(
                    SchemaIssue(
                        path=f"{path_prefix}.pos",
                        message="Missing 'pos' field on lexeme entry.",
                        level="warning",
                    )
                )
            elif not isinstance(pos, str):
                issues.append(
                    SchemaIssue(
                        path=f"{path_prefix}.pos",
                        message="'pos' field must be a string (e.g. 'NOUN', 'ADJ').",
                        level="error",
                    )
                )

    return issues


def _iter_lemma_sections(data: Mapping[str, Any]) -> Iterable[tuple[str, Any, bool]]:
    """
    Yield (section_name, section_obj, require_pos_flag).

    `require_pos_flag` indicates whether we strongly expect POS info
    in this section (professions, nationalities, etc. often have it).
    """
    # (section_name, require_pos)
    candidates = [
        ("entries", True),
        ("lemmas", True),
        ("professions", True),
        ("nationalities", True),
        ("titles", False),
        ("honours", False),
    ]
    for name, require_pos in candidates:
        section = data.get(name)
        if section is not None:
            yield name, section, require_pos


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_schema_version_from_data(data: Dict[str, Any]) -> Optional[int]:
    """
    Best-effort attempt to read the schema_version from a lexicon dict.

    Returns:
        The integer schema version if present and valid, otherwise None.
    """
    meta_raw = data.get("meta") or data.get("_meta")
    if not isinstance(meta_raw, Mapping):
        return None
    ver = meta_raw.get("schema_version")
    return ver if isinstance(ver, int) else None


def validate_lexicon_structure(
    lang_code: str,
    data: Any,
) -> List[SchemaIssue]:
    """
    Validate the structure of a lexicon JSON object.

    Args:
        lang_code:
            Language code (e.g. "en", "fr") used for consistency checks.
        data:
            Parsed JSON object (typically a dict) for the lexicon.

    Returns:
        A list of SchemaIssue objects. An empty list means the lexicon
        passes all checks.

    This function is intentionally forgiving: it focuses on structural
    errors and obvious inconsistencies, while only warning on optional
    metadata.
    """
    issues: List[SchemaIssue] = []

    # 1. Top-level must be a dict
    issues.extend(_ensure_top_level_dict(data))
    if issues and any(i.level == "error" and i.path == "" for i in issues):
        # If top-level is not a dict, no further checks make sense
        return issues

    assert isinstance(data, dict)  # for type checkers

    # 2. meta / _meta
    issues.extend(_validate_meta(lang_code, data))

    # 3. Known lemma sections
    has_any_section = False
    for name, section, require_pos in _iter_lemma_sections(data):
        has_any_section = True
        issues.extend(_validate_lemma_section(name, section, require_pos=require_pos))

    if not has_any_section:
        issues.append(
            SchemaIssue(
                path="",
                message=(
                    "No known lemma sections found "
                    "(expected one of: entries, lemmas, professions, "
                    "nationalities, titles, honours)."
                ),
                level="warning",
            )
        )

    return issues


def raise_if_invalid(lang_code: str, data: Any) -> None:
    """
    Validate a lexicon and raise a ValueError if any *errors* are found.

    Warnings do not cause an exception.

    Raises:
        ValueError if at least one SchemaIssue with level == 'error'
        is produced by validate_lexicon_structure.
    """
    issues = validate_lexicon_structure(lang_code, data)
    errors = [i for i in issues if i.level == "error"]
    if not errors:
        return

    messages = "; ".join(f"{e.path}: {e.message}" for e in errors)
    raise ValueError(f"Lexicon for {lang_code!r} failed schema validation: {messages}")


__all__ = [
    "SCHEMA_VERSION",
    "SchemaIssue",
    "get_schema_version_from_data",
    "validate_lexicon_structure",
    "raise_if_invalid",
]
