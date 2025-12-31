# app/adapters/persistence/lexicon/loader.py
# lexicon/loader.py
"""
lexicon/loader.py
=================

Helpers to load and normalize per-language lexicon files from domain-sharded folders.

Goals
-----
- Provide a single entry point to load lexicon data from data/lexicon/{lang}/.
- Merge multiple domain files (core.json, people.json, science.json, etc.) into a single runtime dictionary.
- Hide filesystem details behind `lexicon.config`.
- Normalize schema differences (handling V2 "entries" vs legacy "lemmas").
- For callers, expose a flattened mapping:

    load_lexicon(lang_code) -> Dict[str, Dict[str, Any]]

  where keys are lemma / surface strings (e.g. "physicienne", "polonais")
  and values are feature bundles (POS, gender, semantic class, etc.).

Enterprise-grade behaviors
--------------------------
- Deterministic loading + override order:
  - files are loaded in sorted filename order
  - per-surface-key collisions can be logged (optional)
- Resilient parsing:
  - corrupt JSON files are skipped with warnings
  - non-dict roots are skipped
- Optional schema validation integration:
  - validate lexicon file structure (warn/error) if `lexicon.schema` is available
- Configurable soft limits:
  - `LexiconConfig.max_lemmas_per_language` can cap the merged map size
- Robust normalization:
  - canonicalization of surface keys via `lexicon.normalization.normalize_for_lookup`
    can be enabled without breaking legacy behavior (see flags below)

Error behaviour
---------------
- If the directory for a language does not exist, `load_lexicon(lang)`
  raises `FileNotFoundError`.
- Individual corrupt JSON files log a warning but do not crash the whole load
  (unless the directory is empty/invalid).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from lexicon.config import get_config

logger = logging.getLogger(__name__)

# Optional imports: keep loader usable in constrained environments
try:
    from lexicon.schema import validate_lexicon_structure  # type: ignore
except Exception:  # pragma: no cover
    validate_lexicon_structure = None  # type: ignore[assignment]

try:
    from lexicon.normalization import normalize_for_lookup  # type: ignore
except Exception:  # pragma: no cover
    normalize_for_lookup = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Internal policy knobs (safe defaults)
# ---------------------------------------------------------------------------

# Keep legacy behavior by default: do not normalize output keys unless enabled.
# (Normalization can be turned on by setting AW_LEXICON_NORMALIZE_KEYS=1)
def _env_flag(name: str) -> bool:
    import os

    raw = os.getenv(name, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


_NORMALIZE_OUTPUT_KEYS: bool = _env_flag("AW_LEXICON_NORMALIZE_KEYS")

# Log collisions when merging. Useful in CI; can be noisy in prod.
_LOG_COLLISIONS: bool = _env_flag("AW_LEXICON_LOG_COLLISIONS")

# If true, schema validation issues with level "error" will fail load for that file.
# If false, schema issues are warnings only.
_SCHEMA_STRICT: bool = _env_flag("AW_LEXICON_SCHEMA_STRICT")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    """Infer the project root as the parent of this package directory."""
    return Path(__file__).resolve().parent.parent


def _lexicon_base_dir() -> Path:
    """
    Resolve the root directory where lexicon folders live.
    Uses `lexicon.config.get_config()`.
    """
    cfg = get_config()
    lex_dir = Path(cfg.lexicon_dir)
    if not lex_dir.is_absolute():
        lex_dir = _project_root() / lex_dir
    return lex_dir


def _language_dir(lang_code: str) -> Path:
    """
    Compute the path to the directory for a given language code.
    e.g., "fr" -> <lexicon_base>/fr/
    """
    return _lexicon_base_dir() / lang_code


# ---------------------------------------------------------------------------
# Load result (internal)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _LoadedFile:
    path: Path
    data: Dict[str, Any]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_json_file(path: Path) -> Dict[str, Any]:
    """
    Load a single JSON file. Returns empty dict on failure (logs warning).
    """
    if not path.is_file():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("Skipping %s: root must be a JSON object (dict).", path.name)
            return {}
        return data
    except json.JSONDecodeError as e:
        logger.warning("Skipping %s: JSON decode error: %s", path.name, e)
        return {}
    except OSError as e:
        logger.warning("Skipping %s: read error: %s", path.name, e)
        return {}


def _maybe_validate(lang_code: str, path: Path, raw_data: Dict[str, Any]) -> bool:
    """
    If schema validator is available, validate file and log issues.

    Returns True if file should be accepted; False if it should be rejected.
    """
    if validate_lexicon_structure is None:
        return True

    try:
        issues = validate_lexicon_structure(lang_code, raw_data, strict=_SCHEMA_STRICT)  # type: ignore[misc]
    except TypeError:
        # Backwards compatibility if validator doesn't support strict=
        issues = validate_lexicon_structure(lang_code, raw_data)  # type: ignore[misc]

    if not issues:
        return True

    # Log issues deterministically
    errors = [i for i in issues if getattr(i, "level", "error") == "error"]
    warnings = [i for i in issues if getattr(i, "level", "error") != "error"]

    for w in sorted(warnings, key=lambda x: (x.path, x.message)):
        logger.warning("Lexicon schema warning in %s (%s): %s", path.name, w.path, w.message)

    for e in sorted(errors, key=lambda x: (x.path, x.message)):
        logger.error("Lexicon schema error in %s (%s): %s", path.name, e.path, e.message)

    if _SCHEMA_STRICT and errors:
        logger.error("Rejecting %s due to schema errors (strict mode).", path.name)
        return False

    return True


def _iter_entry_sources(raw_data: Dict[str, Any]) -> Iterable[Mapping[str, Any]]:
    """
    Yield each lemma map section found in a raw lexicon file dict, in priority order.
    Supports Schema V2 ("entries") and Legacy V1 ("lemmas", "professions", etc.).
    """
    # Priority 1: New Standard "entries"
    entries = raw_data.get("entries")
    if isinstance(entries, Mapping):
        yield entries

    # Priority 2: Legacy "lemmas"
    lemmas = raw_data.get("lemmas")
    if isinstance(lemmas, Mapping):
        yield lemmas

    # Priority 3: Legacy Category Keys (fallback for imperfect migrations)
    for cat in ("professions", "titles", "nationalities", "honours"):
        sec = raw_data.get(cat)
        if isinstance(sec, Mapping):
            yield sec


def _coerce_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip()
        return s if s else None
    return str(x).strip() or None


def _normalize_entry(base_key: str, entry: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Convert a single raw entry into a dictionary of surface_form -> features.

    Expands "forms" and emits one record per surface form.

    Output features are best-effort and stable:
      - pos (if present)
      - human (bool|None)
      - gender (str|None)
      - number (str|None) only for derived forms with explicit tags
      - nationality (bool) if inferred
      - qid (str|None)

    NOTE: This function does not mutate input.
    """
    normalized_map: Dict[str, Dict[str, Any]] = {}

    pos = entry.get("pos")
    gender = entry.get("gender")
    semantic_class = entry.get("semantic_class") or entry.get("category")  # legacy support
    nationality_flag = entry.get("nationality")

    # Profession -> human = True (unless specified)
    human_flag: Optional[bool]
    if isinstance(entry.get("human"), bool):
        human_flag = entry.get("human")  # type: ignore[assignment]
    elif semantic_class == "profession":
        human_flag = True
    else:
        human_flag = None

    # Nationality/demonym -> nationality = True (unless specified)
    if isinstance(nationality_flag, bool):
        nat_flag: Optional[bool] = nationality_flag
    elif semantic_class in ("demonym", "nationality"):
        nat_flag = True
    else:
        nat_flag = None

    qid = entry.get("qid") or entry.get("wikidata_qid")
    qid_s = _coerce_str(qid)

    base_features: Dict[str, Any] = {
        "pos": pos,
        "human": human_flag,
        "gender": gender,
        "qid": qid_s,
    }
    if nat_flag is not None:
        base_features["nationality"] = nat_flag

    # 1) Head lemma
    head_lemma = _coerce_str(entry.get("lemma")) or _coerce_str(base_key) or ""
    if head_lemma:
        normalized_map[head_lemma] = dict(base_features)

    # 2) Surface forms from "forms"
    forms = entry.get("forms")
    if isinstance(forms, Mapping):
        for tag, surface in forms.items():
            surface_s = _coerce_str(surface)
            if not surface_s:
                continue

            feat = dict(base_features)

            # Refine gender/number from tags like "f.sg" / "m.pl"
            if isinstance(tag, str) and tag.strip():
                parts = [p.strip() for p in tag.split(".") if p.strip()]
                g_tag: Optional[str] = parts[0] if parts else None
                n_tag: Optional[str] = parts[1] if len(parts) > 1 else None

                if g_tag in {"m", "f", "n", "common", "neut"}:
                    feat["gender"] = g_tag
                if n_tag in {"sg", "pl"}:
                    feat["number"] = n_tag

            normalized_map[surface_s] = feat

    return normalized_map


def _process_file_content(raw_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Extract lemma/surface mappings from a raw file content dict.
    """
    extracted: Dict[str, Dict[str, Any]] = {}

    for source_dict in _iter_entry_sources(raw_data):
        # Deterministic iteration
        items: List[Tuple[Any, Any]] = list(source_dict.items())
        try:
            items.sort(key=lambda kv: str(kv[0]))
        except Exception:
            pass

        for key, entry in items:
            if not isinstance(entry, Mapping):
                continue
            base_key = _coerce_str(key) or ""
            if not base_key:
                continue
            extracted.update(_normalize_entry(base_key, entry))

    return extracted


def _maybe_normalize_output_keys(mapping: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Optionally normalize output keys using lexicon.normalization.normalize_for_lookup.
    Keeps first-writer-wins semantics on collisions for determinism.
    """
    if not _NORMALIZE_OUTPUT_KEYS:
        return mapping
    if normalize_for_lookup is None:
        logger.warning("AW_LEXICON_NORMALIZE_KEYS enabled but normalize_for_lookup is unavailable.")
        return mapping

    out: Dict[str, Dict[str, Any]] = {}
    for raw_k, feats in mapping.items():
        if not isinstance(raw_k, str):
            continue
        nk = normalize_for_lookup(raw_k)  # type: ignore[misc]
        if not nk:
            continue
        if nk in out and _LOG_COLLISIONS:
            logger.warning("Normalized key collision: %r -> %r (kept first).", raw_k, nk)
            continue
        out.setdefault(nk, feats)
    return out


def _apply_soft_limit(master: Dict[str, Dict[str, Any]], max_items: int) -> Dict[str, Dict[str, Any]]:
    """
    Apply a soft cap to the merged lexicon size in a deterministic way.
    Keeps the first N keys in sorted order.
    """
    if max_items <= 0:
        return master
    if len(master) <= max_items:
        return master
    keys = sorted(master.keys())
    limited_keys = keys[:max_items]
    return {k: master[k] for k in limited_keys}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_lexicon(lang_code: str) -> Dict[str, Dict[str, Any]]:
    """
    Load and merge all lexicon files for a given language code.

    Scans data/lexicon/{lang_code}/*.json.

    Args:
        lang_code: Language code such as "fr", "pt", "ru".

    Returns:
        A mapping: { "surface_form": { features... }, ... }

    Raises:
        FileNotFoundError: if the language directory does not exist.
        ValueError: if lang_code is empty/invalid.
    """
    lang = (lang_code or "").strip()
    if not lang:
        raise ValueError("Language code must be a non-empty string.")

    cfg = get_config()
    lang_dir = _language_dir(lang)

    # Legacy fallback: <lexicon_base>/<lang>_lexicon.json
    if not lang_dir.is_dir():
        legacy_file = _lexicon_base_dir() / f"{lang}_lexicon.json"
        if legacy_file.is_file():
            logger.warning("Loading legacy single-file lexicon for %r", lang)
            raw = _load_json_file(legacy_file)
            if raw and _maybe_validate(lang, legacy_file, raw):
                merged = _process_file_content(raw)
                merged = _maybe_normalize_output_keys(merged)
                return _apply_soft_limit(merged, int(getattr(cfg, "max_lemmas_per_language", 0) or 0))
            return {}
        raise FileNotFoundError(f"Lexicon directory not found: {lang_dir}")

    master: Dict[str, Dict[str, Any]] = {}
    files_processed = 0

    json_files = sorted(lang_dir.glob("*.json"))
    for file_path in json_files:
        raw_data = _load_json_file(file_path)
        if not raw_data:
            continue

        if not _maybe_validate(lang, file_path, raw_data):
            continue

        file_lemmas = _process_file_content(raw_data)
        if not file_lemmas:
            files_processed += 1
            continue

        # Deterministic merge with optional collision logging
        if _LOG_COLLISIONS:
            for k in file_lemmas.keys():
                if k in master:
                    logger.warning(
                        "Lexicon key collision for lang=%s: %r overridden by %s",
                        lang,
                        k,
                        file_path.name,
                    )

        master.update(file_lemmas)
        files_processed += 1

    if files_processed == 0:
        logger.warning("Lexicon folder for %r exists but contains no valid JSON files.", lang)

    master = _maybe_normalize_output_keys(master)

    # Soft limit, if configured
    max_items = int(getattr(cfg, "max_lemmas_per_language", 0) or 0)
    master = _apply_soft_limit(master, max_items)

    return master


def available_languages() -> List[str]:
    """
    Return a sorted list of language codes for which a lexicon directory exists.
    """
    lex_dir = _lexicon_base_dir()
    if not lex_dir.is_dir():
        return []

    langs: List[str] = []
    for item in lex_dir.iterdir():
        if item.is_dir() and any(item.glob("*.json")):
            langs.append(item.name)

    # Legacy fallback: check for root *_lexicon.json files
    for item in lex_dir.glob("*_lexicon.json"):
        code = item.name.replace("_lexicon.json", "")
        if code and code not in langs:
            langs.append(code)

    return sorted(langs)


__all__ = [
    "load_lexicon",
    "available_languages",
]
