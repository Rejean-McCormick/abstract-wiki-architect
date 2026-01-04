# app/adapters/persistence/lexicon/loader.py
"""
lexicon/loader.py
=================

Enterprise-grade loader for per-language lexicon data.

What it loads
-------------
Lexica live under a directory configured via `lexicon.config`:

    data/lexicon/
      fr/
        core.json
        people.json
        ...
      en/
        ...

Each file is a JSON object and may contain (Schema V2 preferred):

    {
      "_meta": {...},
      "entries": { ... }
    }

Legacy sections are also supported:
    - "lemmas"
    - "professions"
    - "nationalities"
    - "titles"
    - "honours"

Legacy-flat root entries are supported too (common in older tests/tools):
    {
      "meta": {...},
      "physicien": {...},
      "polonais": {...}
    }

What it returns
---------------
This loader returns a `lexicon.types.Lexicon` (the enterprise-grade runtime object)
because `lexicon.index.LexiconIndex` is built over a Lexicon instance.

For backwards compatibility, a helper `load_lexicon_flat()` is provided to return
a flattened {surface -> features} mapping similar to older code paths.

Enterprise-grade behaviors
--------------------------
- Deterministic loading/override order: files are processed in sorted filename order.
- Resilient parsing: corrupt JSON files are skipped with warnings.
- Optional schema validation integration (if `lexicon.schema` is available):
  - issues are logged; strict mode rejects files with "error" issues.
  - legacy-flat files are normalized into a schema-like shape for validation.
- Configurable soft limits: `LexiconConfig.max_lemmas_per_language` caps total entries.
- Explicit collision behavior: last writer wins, optionally logged.

Error behaviour
---------------
- If the directory for a language does not exist, `load_lexicon()` raises FileNotFoundError
  (with a legacy single-file fallback <base>/<lang>_lexicon.json).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from app.shared.config import settings  # robust path resolution

from .config import get_config
from .types import (
    BaseLexicalEntry,
    HonourEntry,
    Lexicon,
    LexiconMeta,
    NationalityEntry,
    ProfessionEntry,
    TitleEntry,
)

logger = logging.getLogger(__name__)

# Optional imports: keep loader usable in constrained environments.
try:
    from .schema import validate_lexicon_structure
except Exception:  # pragma: no cover
    validate_lexicon_structure = None

try:
    from .normalization import normalize_for_lookup
except Exception:  # pragma: no cover
    normalize_for_lookup = None


# ---------------------------------------------------------------------------
# Internal policy knobs (safe defaults)
# ---------------------------------------------------------------------------

def _env_flag(name: str) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


_LOG_COLLISIONS: bool = _env_flag("AW_LEXICON_LOG_COLLISIONS")
_SCHEMA_STRICT: bool = _env_flag("AW_LEXICON_SCHEMA_STRICT")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _find_repo_root(start: Path) -> Path:
    """
    Best-effort repository root detection.
    Prioritizes settings.FILESYSTEM_REPO_PATH if available to avoid CWD dependency issues.
    """
    if getattr(settings, "FILESYSTEM_REPO_PATH", None):
        configured_path = Path(settings.FILESYSTEM_REPO_PATH).resolve()
        if configured_path.exists():
            return configured_path

    markers = ("pyproject.toml", "setup.cfg", "setup.py", ".git")
    cur = start.resolve()
    for _ in range(10):
        for m in markers:
            if (cur / m).exists():
                return cur
        if cur.parent == cur:
            break
        cur = cur.parent

    try:
        return start.resolve().parents[4]
    except Exception:
        return start.resolve().parent


def _project_root() -> Path:
    return _find_repo_root(Path(__file__).resolve().parent)


def _lexicon_base_dir() -> Path:
    cfg = get_config()
    lex_dir = Path(cfg.lexicon_dir)
    if not lex_dir.is_absolute():
        lex_dir = _project_root() / lex_dir
    return lex_dir


def _language_dir(lang_code: str) -> Path:
    return _lexicon_base_dir() / lang_code


# ---------------------------------------------------------------------------
# Internal load result
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _LoadedFile:
    path: Path
    data: Dict[str, Any]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json_file(path: Path) -> Dict[str, Any]:
    """Load a single JSON file. Returns empty dict on failure (logs warning)."""
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


def _coerce_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip()
        return s if s else None
    s = str(x).strip()
    return s if s else None


def _extract_meta(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    meta = raw.get("meta") or raw.get("_meta")
    return meta if isinstance(meta, dict) else None


# Reserved top-level keys for legacy-flat detection.
_RESERVED_TOPLEVEL_KEYS = {
    "meta",
    "_meta",
    "entries",
    "lemmas",
    "professions",
    "nationalities",
    "titles",
    "honours",
}

def _legacy_flat_root_entries(raw_data: Dict[str, Any]) -> Dict[str, Mapping[str, Any]]:
    """
    Legacy-flat: treat non-reserved top-level mapping items as entries
    e.g. {"meta": {...}, "physicien": {...}, "polonais": {...}}
    """
    root_entries: Dict[str, Mapping[str, Any]] = {}
    for k, v in raw_data.items():
        if k in _RESERVED_TOPLEVEL_KEYS:
            continue
        if isinstance(v, Mapping):
            root_entries[str(k)] = v
    return root_entries


def _sanitize_for_validation(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a schema-ish shape for schema validation without mutating the original.
    Also normalizes meta.schema_version to int when it is a numeric string.
    """
    meta = _extract_meta(raw_data) or {}
    meta_copy: Dict[str, Any] = dict(meta)

    sv = meta_copy.get("schema_version")
    if isinstance(sv, str):
        s = sv.strip()
        if s.isdigit():
            meta_copy["schema_version"] = int(s)

    # If the file is legacy-flat (no known lemma sections), normalize it so the validator
    # sees entries and doesn't spam "no known lemma sections".
    has_known_sections = any(
        isinstance(raw_data.get(k), Mapping)
        for k in ("entries", "lemmas", "professions", "nationalities", "titles", "honours")
    )

    if not has_known_sections:
        root = _legacy_flat_root_entries(raw_data)
        if root:
            return {"meta": meta_copy, "entries": dict(root)}

    # Otherwise validate the original shape but with normalized meta if present.
    if _extract_meta(raw_data) is None:
        return dict(raw_data)

    out = dict(raw_data)
    if "meta" in out and isinstance(out.get("meta"), dict):
        out["meta"] = meta_copy
    if "_meta" in out and isinstance(out.get("_meta"), dict):
        out["_meta"] = meta_copy
    return out


def _maybe_validate(lang_code: str, path: Path, raw_data: Dict[str, Any]) -> bool:
    """
    If schema validator is available, validate file and log issues.

    Returns True if file should be accepted; False if it should be rejected.
    """
    if validate_lexicon_structure is None:
        return True

    payload = _sanitize_for_validation(raw_data)

    try:
        issues = validate_lexicon_structure(lang_code, payload)  # type: ignore[misc]
    except Exception as e:
        logger.warning("Schema validation failed for %s: %s (accepting file).", path.name, e)
        return True

    if not issues:
        return True

    def _lvl(x: Any) -> str:
        return str(getattr(x, "level", "error") or "error").lower()

    errors = [i for i in issues if _lvl(i) == "error"]
    warnings = [i for i in issues if _lvl(i) != "error"]

    for w in sorted(warnings, key=lambda x: (getattr(x, "path", ""), getattr(x, "message", ""))):
        logger.warning(
            "Lexicon schema warning in %s (%s): %s",
            path.name,
            getattr(w, "path", ""),
            getattr(w, "message", ""),
        )

    for e in sorted(errors, key=lambda x: (getattr(x, "path", ""), getattr(x, "message", ""))):
        logger.error(
            "Lexicon schema error in %s (%s): %s",
            path.name,
            getattr(e, "path", ""),
            getattr(e, "message", ""),
        )

    if _SCHEMA_STRICT and errors:
        logger.error("Rejecting %s due to schema errors (strict mode).", path.name)
        return False

    return True


def _merge_meta(lang: str, metas: List[Tuple[Path, Dict[str, Any]]]) -> LexiconMeta:
    """
    Merge meta blocks into a single LexiconMeta.
    First-writer wins for canonical fields; extra accumulates.
    """
    language = lang
    family: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    extra: Dict[str, Any] = {}

    for path, m in metas:
        m_lang = _coerce_str(m.get("language"))
        if m_lang and m_lang != language:
            logger.warning(
                "Meta language mismatch in %s: %r (expected %r).",
                path.name,
                m_lang,
                language,
            )

        if family is None:
            family = _coerce_str(m.get("family"))
        if version is None:
            version = _coerce_str(m.get("version"))
        if description is None:
            description = _coerce_str(m.get("description"))

        for k, v in m.items():
            if k in {"language", "family", "version", "description"}:
                continue
            if k == "schema_version":
                # normalize numeric string -> int
                if isinstance(v, str) and v.strip().isdigit():
                    v = int(v.strip())
            if k not in extra:
                extra[k] = v

    return LexiconMeta(
        language=language,
        family=family,
        version=version,
        description=description,
        extra=extra,
    )


def _iter_entry_sources(raw_data: Dict[str, Any]) -> Iterable[Tuple[str, Mapping[str, Any]]]:
    """
    Yield (section_name, mapping) for each lemma-bearing section in priority order.

    Priority:
      1) Schema V2 "entries"
      2) Legacy "lemmas"
      3) Explicit legacy category maps
      4) Legacy-flat root entries (all other mapping values at top-level)
    """
    entries = raw_data.get("entries")
    if isinstance(entries, Mapping):
        yield "entries", entries

    lemmas = raw_data.get("lemmas")
    if isinstance(lemmas, Mapping):
        yield "lemmas", lemmas

    for cat in ("professions", "nationalities", "titles", "honours"):
        sec = raw_data.get(cat)
        if isinstance(sec, Mapping):
            yield cat, sec

    root_entries = _legacy_flat_root_entries(raw_data)
    if root_entries:
        yield "root", root_entries


def _take_forms(entry: Mapping[str, Any]) -> Dict[str, str]:
    forms = entry.get("forms")
    if not isinstance(forms, Mapping):
        return {}
    out: Dict[str, str] = {}
    for k, v in forms.items():
        ks = _coerce_str(k)
        vs = _coerce_str(v)
        if ks and vs:
            out[ks] = vs
    return out


def _entry_common_fields(lang: str, key: str, entry: Mapping[str, Any]) -> Dict[str, Any]:
    lemma = _coerce_str(entry.get("lemma")) or key
    pos = _coerce_str(entry.get("pos")) or "NOUN"

    semantic = (
        _coerce_str(entry.get("semantic_class"))
        or _coerce_str(entry.get("sense"))
        or _coerce_str(entry.get("category"))
    )
    human_val = entry.get("human") if isinstance(entry.get("human"), bool) else None
    gender = _coerce_str(entry.get("gender"))
    default_number = _coerce_str(entry.get("default_number"))
    default_formality = _coerce_str(entry.get("default_formality"))
    qid = _coerce_str(entry.get("wikidata_qid") or entry.get("qid"))
    forms = _take_forms(entry)

    used = {
        "lemma",
        "pos",
        "semantic_class",
        "sense",
        "category",
        "human",
        "gender",
        "default_number",
        "default_formality",
        "wikidata_qid",
        "qid",
        "forms",
    }
    extra: Dict[str, Any] = {k: v for k, v in entry.items() if k not in used}

    return {
        "key": key,
        "lemma": lemma,
        "pos": pos,
        "language": lang,
        "sense": semantic,
        "human": human_val,
        "gender": gender,
        "default_number": default_number,
        "default_formality": default_formality,
        "wikidata_qid": qid,
        "forms": forms,
        "extra": extra,
    }


def _to_profession(lang: str, key: str, entry: Mapping[str, Any]) -> ProfessionEntry:
    fields = _entry_common_fields(lang, key, entry)
    if not fields.get("sense"):
        fields["sense"] = "profession"
    return ProfessionEntry(**fields)  # type: ignore[arg-type]


def _to_nationality(lang: str, key: str, entry: Mapping[str, Any]) -> NationalityEntry:
    fields = _entry_common_fields(lang, key, entry)

    adjective = _coerce_str(entry.get("adjective"))
    demonym = _coerce_str(entry.get("demonym"))
    country_name = _coerce_str(entry.get("country_name"))

    extra = dict(fields.get("extra") or {})
    for k in ("adjective", "demonym", "country_name"):
        extra.pop(k, None)
    fields["extra"] = extra

    return NationalityEntry(
        **fields,  # type: ignore[arg-type]
        adjective=adjective,
        demonym=demonym,
        country_name=country_name,
    )


def _to_title(lang: str, key: str, entry: Mapping[str, Any]) -> TitleEntry:
    fields = _entry_common_fields(lang, key, entry)
    position = _coerce_str(entry.get("position"))

    extra = dict(fields.get("extra") or {})
    extra.pop("position", None)
    fields["extra"] = extra

    return TitleEntry(**fields, position=position)  # type: ignore[arg-type]


def _to_honour(key: str, entry: Mapping[str, Any]) -> HonourEntry:
    label = _coerce_str(entry.get("label")) or _coerce_str(entry.get("lemma")) or key
    short_label = _coerce_str(entry.get("short_label"))
    qid = _coerce_str(entry.get("wikidata_qid") or entry.get("qid"))

    used = {"label", "lemma", "short_label", "wikidata_qid", "qid"}
    extra: Dict[str, Any] = {k: v for k, v in entry.items() if k not in used}

    return HonourEntry(
        key=key,
        label=label,
        short_label=short_label,
        wikidata_qid=qid,
        extra=extra,
    )


def _to_general(lang: str, key: str, entry: Mapping[str, Any]) -> BaseLexicalEntry:
    fields = _entry_common_fields(lang, key, entry)
    return BaseLexicalEntry(**fields)  # type: ignore[arg-type]


def _merge_entry(
    table: Dict[str, Any],
    key: str,
    value: Any,
    *,
    lang: str,
    file_name: str,
) -> None:
    if not key:
        return
    if _LOG_COLLISIONS and key in table:
        logger.warning("Lexicon collision lang=%s key=%r overridden by %s", lang, key, file_name)
    table[key] = value


def _apply_soft_limit(lex: Lexicon, max_items: int) -> None:
    """
    Apply a soft cap to the total number of entries in a deterministic way.
    """
    if max_items <= 0:
        return

    tables: List[Tuple[str, Dict[str, Any]]] = [
        ("professions", lex.professions),
        ("nationalities", lex.nationalities),
        ("titles", lex.titles),
        ("honours", lex.honours),
        ("general_entries", lex.general_entries),
    ]

    ordered: List[Tuple[str, str]] = []
    for name, tbl in tables:
        for k in sorted(tbl.keys()):
            ordered.append((name, k))

    if len(ordered) <= max_items:
        return

    keep = set(ordered[:max_items])

    for name, tbl in tables:
        drop = [k for k in list(tbl.keys()) if (name, k) not in keep]
        for k in drop:
            del tbl[k]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_lexicon(lang_code: str) -> Lexicon:
    """
    Load and merge all lexicon files for a given language code.

    Returns:
        lexicon.types.Lexicon
    """
    lang = (lang_code or "").strip()
    if not lang:
        raise ValueError("Language code must be a non-empty string.")

    cfg = get_config()
    lang_dir = _language_dir(lang)

    loaded_files: List[_LoadedFile] = []

    if not lang_dir.is_dir():
        legacy_file = _lexicon_base_dir() / f"{lang}_lexicon.json"
        if legacy_file.is_file():
            logger.warning("Loading legacy single-file lexicon for %r", lang)
            raw = _load_json_file(legacy_file)
            if raw and _maybe_validate(lang, legacy_file, raw):
                loaded_files.append(_LoadedFile(path=legacy_file, data=raw))
        else:
            raise FileNotFoundError(f"Lexicon directory not found: {lang_dir}")
    else:
        json_files = sorted(lang_dir.glob("*.json"))
        for file_path in json_files:
            raw = _load_json_file(file_path)
            if not raw:
                continue
            if not _maybe_validate(lang, file_path, raw):
                continue
            loaded_files.append(_LoadedFile(path=file_path, data=raw))

    if not loaded_files:
        raise FileNotFoundError(f"No valid lexicon JSON files found for language: {lang!r}")

    metas: List[Tuple[Path, Dict[str, Any]]] = []
    for lf in loaded_files:
        m = _extract_meta(lf.data)
        if m is not None:
            metas.append((lf.path, m))
    meta = _merge_meta(lang, metas) if metas else LexiconMeta(language=lang)

    lex = Lexicon(meta=meta)

    lex.raw = {
        "files": [lf.path.name for lf in loaded_files],
    }

    for lf in sorted(loaded_files, key=lambda x: x.path.name):
        raw = lf.data
        file_name = lf.path.name

        for section_name, mapping in _iter_entry_sources(raw):
            items: List[Tuple[Any, Any]] = list(mapping.items())
            try:
                items.sort(key=lambda kv: str(kv[0]))
            except Exception:
                pass

            for k_raw, v in items:
                if not isinstance(v, Mapping):
                    continue

                key = _coerce_str(k_raw) or ""
                if not key:
                    continue

                if section_name == "professions":
                    _merge_entry(lex.professions, key, _to_profession(lang, key, v), lang=lang, file_name=file_name)
                    continue
                if section_name == "nationalities":
                    _merge_entry(lex.nationalities, key, _to_nationality(lang, key, v), lang=lang, file_name=file_name)
                    continue
                if section_name == "titles":
                    _merge_entry(lex.titles, key, _to_title(lang, key, v), lang=lang, file_name=file_name)
                    continue
                if section_name == "honours":
                    _merge_entry(lex.honours, key, _to_honour(key, v), lang=lang, file_name=file_name)
                    continue

                semantic = (
                    str(v.get("semantic_class") or v.get("sense") or v.get("category") or "")
                    .strip()
                    .lower()
                )

                # Heuristic routing for legacy-flat/root and for entries lacking semantic tags.
                pos = str(v.get("pos") or "").strip().upper()
                human = v.get("human") if isinstance(v.get("human"), bool) else None

                if semantic in {"profession", "occupation"}:
                    _merge_entry(lex.professions, key, _to_profession(lang, key, v), lang=lang, file_name=file_name)
                elif semantic in {"nationality", "demonym"}:
                    _merge_entry(lex.nationalities, key, _to_nationality(lang, key, v), lang=lang, file_name=file_name)
                elif semantic == "title":
                    _merge_entry(lex.titles, key, _to_title(lang, key, v), lang=lang, file_name=file_name)
                elif semantic in {"honour", "honor", "award"}:
                    _merge_entry(lex.honours, key, _to_honour(key, v), lang=lang, file_name=file_name)
                else:
                    if not semantic:
                        # Strong signals first
                        if pos in {"ADJ", "ADJECTIVE"}:
                            _merge_entry(
                                lex.nationalities,
                                key,
                                _to_nationality(lang, key, v),
                                lang=lang,
                                file_name=file_name,
                            )
                            continue
                        if human is True:
                            _merge_entry(
                                lex.professions,
                                key,
                                _to_profession(lang, key, v),
                                lang=lang,
                                file_name=file_name,
                            )
                            continue
                        # Legacy-flat bias: treat NOUNs as professions (common in old bio lexica)
                        if section_name == "root" and pos in {"NOUN", ""}:
                            _merge_entry(
                                lex.professions,
                                key,
                                _to_profession(lang, key, v),
                                lang=lang,
                                file_name=file_name,
                            )
                            continue

                    _merge_entry(lex.general_entries, key, _to_general(lang, key, v), lang=lang, file_name=file_name)

    max_items = int(getattr(cfg, "max_lemmas_per_language", 0) or 0)
    _apply_soft_limit(lex, max_items)

    return lex


def load_lexicon_flat(lang_code: str) -> Dict[str, Dict[str, Any]]:
    """
    Backwards-compatible helper: flatten a Lexicon into {surface -> features}.
    """
    lex = load_lexicon(lang_code)

    normalize_keys = _env_flag("AW_LEXICON_NORMALIZE_KEYS") and normalize_for_lookup is not None

    out: Dict[str, Dict[str, Any]] = {}

    def add(surface: str, feats: Dict[str, Any]) -> None:
        if not surface:
            return
        key = surface
        if normalize_keys:
            nk = normalize_for_lookup(surface)  # type: ignore[misc]
            if not nk:
                return
            key = nk
        out.setdefault(key, feats)

    def pack_base(e: BaseLexicalEntry) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "pos": e.pos,
            "gender": e.gender,
            "human": e.human,
            "sense": e.sense,
            "qid": e.wikidata_qid,
        }
        if e.extra:
            d.update(e.extra)
        return d

    for e in lex.professions.values():
        base = pack_base(e)
        add(e.lemma, dict(base))
        for _, s in (e.forms or {}).items():
            add(s, dict(base))

    for e in lex.nationalities.values():
        base = pack_base(e)
        add(e.lemma, dict(base))
        if e.adjective:
            add(e.adjective, dict(base))
        if e.demonym:
            add(e.demonym, dict(base))
        if e.country_name:
            add(e.country_name, dict(base))
        for _, s in (e.forms or {}).items():
            add(s, dict(base))

    for e in lex.titles.values():
        base = pack_base(e)
        add(e.lemma, dict(base))
        for _, s in (e.forms or {}).items():
            add(s, dict(base))

    for e in lex.general_entries.values():
        base = pack_base(e)
        add(e.lemma, dict(base))
        for _, s in (e.forms or {}).items():
            add(s, dict(base))

    for h in lex.honours.values():
        feats: Dict[str, Any] = {
            "pos": "HONOUR",
            "qid": h.wikidata_qid,
        }
        if h.extra:
            feats.update(h.extra)
        add(h.label, dict(feats))
        if h.short_label:
            add(h.short_label, dict(feats))

    return out


def available_languages() -> List[str]:
    """Return a sorted list of language codes for which a lexicon directory exists."""
    lex_dir = _lexicon_base_dir()
    if not lex_dir.is_dir():
        return []

    langs: List[str] = []
    for item in lex_dir.iterdir():
        if item.is_dir() and any(item.glob("*.json")):
            langs.append(item.name)

    for item in lex_dir.glob("*_lexicon.json"):
        code = item.name.replace("_lexicon.json", "")
        if code and code not in langs:
            langs.append(code)

    return sorted(langs)


__all__ = [
    "load_lexicon",
    "load_lexicon_flat",
    "available_languages",
]
