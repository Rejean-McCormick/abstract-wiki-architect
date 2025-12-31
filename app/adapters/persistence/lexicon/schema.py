# app/adapters/persistence/lexicon/schema.py
# lexicon/schema.py
"""
lexicon/schema.py
=================

Lightweight schema and validation helpers for lexicon JSON files.

The goal is *not* to enforce a huge, fragile specification, but to:

- Ensure basic structural sanity:
  - Top-level object is a dict.
  - Known sections (entries, lemmas, professions, etc.) are dicts.
  - Lemma keys are strings.
  - Each entry has at least a `pos` or equivalent hint where expected.
- Track a simple schema version for future migrations.
- Provide "enterprise-grade" diagnostics:
  - stable paths
  - deterministic ordering
  - configurable strictness (warn vs error)
  - optional deeper checks for common foot-guns (forms types, qid types)

We deliberately avoid depending on external libraries like `jsonschema`:
validation is done with straightforward Python checks so it can run
anywhere, including restricted environments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION: int = 1


# ---------------------------------------------------------------------------
# Public issue model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
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
    level: str = "error"  # "error" | "warning"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _issue(path: str, message: str, *, level: str) -> SchemaIssue:
    if level not in {"error", "warning"}:
        level = "error"
    return SchemaIssue(path=path, message=message, level=level)


def _is_mapping(x: Any) -> bool:
    return isinstance(x, Mapping)


def _ensure_top_level_dict(data: Any, *, strict: bool) -> List[SchemaIssue]:
    if not isinstance(data, dict):
        return [
            _issue(
                path="",
                message="Top-level lexicon JSON must be an object (dict).",
                level="error" if strict else "warning",
            )
        ]
    return []


def _validate_meta(lang_code: str, data: Dict[str, Any], *, strict: bool) -> List[SchemaIssue]:
    issues: List[SchemaIssue] = []
    meta_raw = data.get("meta") or data.get("_meta")

    if meta_raw is None:
        issues.append(
            _issue(
                path="meta",
                message="Missing 'meta'/_meta section; consider adding basic metadata.",
                level="warning",
            )
        )
        return issues

    if not isinstance(meta_raw, dict):
        issues.append(
            _issue(
                path="meta",
                message="'meta'/_meta must be an object (dict).",
                level="error" if strict else "warning",
            )
        )
        return issues

    # language sanity
    lang = meta_raw.get("language")
    if lang is None:
        issues.append(
            _issue(
                path="meta.language",
                message="Missing 'language' field in meta; should match lexicon language code.",
                level="warning",
            )
        )
    elif not isinstance(lang, str):
        issues.append(
            _issue(
                path="meta.language",
                message="'language' field in meta must be a string.",
                level="error" if strict else "warning",
            )
        )
    elif lang_code and lang_code != lang:
        issues.append(
            _issue(
                path="meta.language",
                message=f"Language mismatch: meta.language={lang!r}, expected {lang_code!r}.",
                level="warning",
            )
        )

    # schema version
    schema_ver = meta_raw.get("schema_version")
    if schema_ver is None:
        issues.append(
            _issue(
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
            _issue(
                path="meta.schema_version",
                message="'schema_version' must be an integer.",
                level="error" if strict else "warning",
            )
        )
    elif schema_ver != SCHEMA_VERSION:
        issues.append(
            _issue(
                path="meta.schema_version",
                message=(
                    f"schema_version={schema_ver} does not match "
                    f"current internal schema version {SCHEMA_VERSION}."
                ),
                level="warning",
            )
        )

    return issues


def _iter_lemma_sections(data: Mapping[str, Any]) -> Iterable[Tuple[str, Any, bool]]:
    """
    Yield (section_name, section_obj, require_pos_flag).

    require_pos_flag indicates whether we strongly expect POS info
    in this section.
    """
    candidates: Sequence[Tuple[str, bool]] = [
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


def _validate_forms_map(
    path_prefix: str,
    entry: Mapping[str, Any],
    *,
    strict: bool,
) -> List[SchemaIssue]:
    """
    Validate `forms` if present: must be a mapping of str -> str.
    """
    issues: List[SchemaIssue] = []
    if "forms" not in entry:
        return issues

    forms = entry.get("forms")
    if forms is None:
        return issues

    if not _is_mapping(forms):
        issues.append(
            _issue(
                path=f"{path_prefix}.forms",
                message="'forms' must be an object (dict) mapping tags to strings.",
                level="error" if strict else "warning",
            )
        )
        return issues

    for k, v in forms.items():
        if not isinstance(k, str):
            issues.append(
                _issue(
                    path=f"{path_prefix}.forms",
                    message="All 'forms' keys must be strings.",
                    level="error" if strict else "warning",
                )
            )
            break
        if not isinstance(v, str):
            issues.append(
                _issue(
                    path=f"{path_prefix}.forms.{k!r}",
                    message="All 'forms' values must be strings.",
                    level="error" if strict else "warning",
                )
            )

    return issues


def _validate_qid_fields(
    path_prefix: str,
    entry: Mapping[str, Any],
    *,
    strict: bool,
) -> List[SchemaIssue]:
    """
    Validate common Wikidata identifier fields if present.
    """
    issues: List[SchemaIssue] = []
    for key in ("qid", "wikidata_qid"):
        if key not in entry:
            continue
        v = entry.get(key)
        if v is None:
            continue
        if not isinstance(v, str):
            issues.append(
                _issue(
                    path=f"{path_prefix}.{key}",
                    message=f"'{key}' must be a string if present.",
                    level="error" if strict else "warning",
                )
            )
    return issues


def _validate_lemma_section(
    section_name: str,
    section: Any,
    *,
    require_pos: bool,
    strict: bool,
) -> List[SchemaIssue]:
    """
    Validate a lemma-bearing section such as:
        entries, lemmas, professions, nationalities, titles, honours.

    Assertions:
        - section is a dict-like mapping
        - keys (lemmas) are strings
        - values are dict-like entries
        - optional POS sanity if require_pos=True
        - optional deeper checks for common structures (forms, qid fields)
    """
    issues: List[SchemaIssue] = []

    if not isinstance(section, Mapping):
        issues.append(
            _issue(
                path=section_name,
                message=f"Section '{section_name}' must be an object (dict) mapping lemmas to entries.",
                level="error" if strict else "warning",
            )
        )
        return issues

    # Deterministic ordering for stable CI output
    items: List[Tuple[Any, Any]] = list(section.items())
    try:
        items.sort(key=lambda kv: str(kv[0]))
    except Exception:
        pass

    for lemma, entry in items:
        path_prefix = f"{section_name}.{lemma!r}"

        if not isinstance(lemma, str):
            issues.append(
                _issue(
                    path=section_name,
                    message="Lemma keys must be strings.",
                    level="error" if strict else "warning",
                )
            )
            continue

        if not isinstance(entry, Mapping):
            issues.append(
                _issue(
                    path=path_prefix,
                    message="Entry value must be an object (dict).",
                    level="error" if strict else "warning",
                )
            )
            continue

        # POS checks
        if require_pos:
            pos = entry.get("pos")
            if pos is None:
                issues.append(
                    _issue(
                        path=f"{path_prefix}.pos",
                        message="Missing 'pos' field on lexeme entry.",
                        level="warning" if not strict else "warning",
                    )
                )
            elif not isinstance(pos, str):
                issues.append(
                    _issue(
                        path=f"{path_prefix}.pos",
                        message="'pos' field must be a string (e.g. 'NOUN', 'ADJ').",
                        level="error" if strict else "warning",
                    )
                )

        # Deeper, low-cost validations
        issues.extend(_validate_forms_map(path_prefix, entry, strict=strict))
        issues.extend(_validate_qid_fields(path_prefix, entry, strict=strict))

    return issues


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
    *,
    strict: bool = True,
) -> List[SchemaIssue]:
    """
    Validate the structure of a lexicon JSON object.

    Args:
        lang_code:
            Language code (e.g. "en", "fr") used for consistency checks.
        data:
            Parsed JSON object (typically a dict) for the lexicon.
        strict:
            If True, structural type mismatches are "error".
            If False, some type mismatches degrade to "warning".

    Returns:
        A list of SchemaIssue objects. Empty list means the lexicon passes.
    """
    issues: List[SchemaIssue] = []

    # 1. Top-level must be a dict
    issues.extend(_ensure_top_level_dict(data, strict=strict))
    if issues and any(i.level == "error" and i.path == "" for i in issues):
        return issues

    assert isinstance(data, dict)  # for type checkers

    # 2. meta / _meta
    issues.extend(_validate_meta(lang_code, data, strict=strict))

    # 3. Known lemma sections
    has_any_section = False
    for name, section, require_pos in _iter_lemma_sections(data):
        has_any_section = True
        issues.extend(
            _validate_lemma_section(
                name,
                section,
                require_pos=require_pos,
                strict=strict,
            )
        )

    if not has_any_section:
        issues.append(
            _issue(
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


def raise_if_invalid(
    lang_code: str,
    data: Any,
    *,
    strict: bool = True,
) -> None:
    """
    Validate a lexicon and raise ValueError if any *errors* are found.

    Warnings do not cause an exception.

    Raises:
        ValueError if at least one SchemaIssue with level == "error"
        is produced by validate_lexicon_structure.
    """
    issues = validate_lexicon_structure(lang_code, data, strict=strict)
    errors = [i for i in issues if i.level == "error"]
    if not errors:
        return

    # Deterministic message ordering for CI stability
    errors_sorted = sorted(errors, key=lambda e: (e.path, e.message))
    messages = "; ".join(f"{e.path}: {e.message}" for e in errors_sorted)
    raise ValueError(f"Lexicon for {lang_code!r} failed schema validation: {messages}")


__all__ = [
    "SCHEMA_VERSION",
    "SchemaIssue",
    "get_schema_version_from_data",
    "validate_lexicon_structure",
    "raise_if_invalid",
]
