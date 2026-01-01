# utils/migrate_lexicon_schema.py
"""
utils/migrate_lexicon_schema.py
-------------------------------

One-off / ad-hoc migration script for lexicon JSON files.

Goal
====

Normalize all `data/lexicon/*.json` files to the current schema
(expected by `lexicon/types.py` and `data/lexicon_schema.json`), by:

- Ensuring there is a `meta` block (and not only `_meta`).
- Filling in missing metadata such as `meta.language`.
- Making sure each entry has:
    - `key`
    - `lemma`
    - `pos` (for BaseLexicalEntry-style entries)
    - `language`
    - `forms` (at least an empty object)
    - `extra` (at least an empty object)
- Optionally bumping the metadata version field.

This script is intentionally conservative: it never deletes unknown
fields; it only *adds* missing keys or renames `_meta` -> `meta`.

Usage
=====

From project root:

    python utils/migrate_lexicon_schema.py --all
    python utils/migrate_lexicon_schema.py --file data/lexicon/sw_lexicon.json
    python utils/migrate_lexicon_schema.py --all --dry-run
    python utils/migrate_lexicon_schema.py --all --no-backup

By default it:

- Scans `data/lexicon/*.json`.
- Writes a `.bak` backup next to each migrated file.
- Bumps `meta.version` to 0.2.0 (configurable).

If anything looks wrong, restore from the `.bak` files.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from glob import glob
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Project root & logging
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from utils.logging_setup import get_logger, init_logging

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_language_from_filename(path: str) -> Optional[str]:
    """
    Infer a language code from filename patterns such as:

        data/lexicon/en_lexicon.json  -> en
        data/lexicon/fr_lexicon.json  -> fr
        data/lexicon/sw_lexicon.json  -> sw

    If we cannot infer a language, return None.
    """
    base = os.path.basename(path)
    stem, _ = os.path.splitext(base)

    # Common pattern: "<lang>_lexicon"
    if stem.endswith("_lexicon"):
        lang = stem[: -len("_lexicon")]
        return lang or None

    # As a fallback, if there's an underscore, take everything before it.
    if "_" in stem:
        return stem.split("_", 1)[0]

    # Last resort: use the whole stem (not ideal, but better than nothing).
    return stem or None


def _ensure_meta_block(
    data: Dict[str, Any], path: str, target_version: str
) -> Dict[str, Any]:
    """
    Ensure that the top-level object has a `meta` block, not just `_meta`,
    and that it has a `language` field at minimum.

    Returns the normalized `meta` dict.
    """
    meta = data.get("meta") or data.get("_meta") or {}

    # Remove legacy alias if present
    if "_meta" in data and "meta" not in data:
        log.info("  - Moving _meta -> meta in %s", path)
        data["meta"] = meta
        del data["_meta"]
    else:
        data["meta"] = meta

    # Set language if missing
    if "language" not in meta or not meta.get("language"):
        inferred = _infer_language_from_filename(path)
        if inferred:
            log.info(
                "  - meta.language missing; inferring '%s' from filename.", inferred
            )
            meta["language"] = inferred
        else:
            log.warning(
                "  - Could not infer language for %s; meta.language stays unset.", path
            )

    # Bump version
    old_version = meta.get("version")
    if old_version != target_version:
        log.info("  - Bumping meta.version: %r -> %r", old_version, target_version)
        meta["version"] = target_version

    return meta


def _ensure_base_entry_fields(
    entry: Dict[str, Any],
    entry_key: str,
    language: Optional[str],
    default_pos: Optional[str],
) -> None:
    """
    Ensure required BaseLexicalEntry-style fields exist.

    We DO NOT delete anything; we only add fields if they are missing.
    """
    # key
    if "key" not in entry or not entry["key"]:
        entry["key"] = entry_key

    # lemma
    if "lemma" not in entry or not entry["lemma"]:
        # Fall back to label or key
        lemma = entry.get("label") or entry_key
        entry["lemma"] = lemma

    # pos (if a default_pos is provided; honours do not need it)
    if default_pos and ("pos" not in entry or not entry["pos"]):
        entry["pos"] = default_pos

    # language
    if language and ("language" not in entry or not entry["language"]):
        entry["language"] = language

    # forms
    if "forms" not in entry or entry["forms"] is None:
        entry["forms"] = {}

    # extra
    if "extra" not in entry or entry["extra"] is None:
        entry["extra"] = {}


def _migrate_sections(
    data: Dict[str, Any],
    lex_lang: Optional[str],
    path: str,
) -> None:
    """
    Normalize the known top-level sections:

        professions, nationalities, titles, honours, entries

    Each section is expected to be a dict-of-dicts; we ensure base
    fields for those that are BaseLexicalEntry-like.
    """
    # Section -> default POS (None means do not enforce POS)
    section_pos = {
        "professions": "NOUN",
        "nationalities": "ADJ",
        "titles": "TITLE",
        "entries": "NOUN",
        # "honours" uses its own schema, no POS enforcement
    }

    for section, default_pos in section_pos.items():
        entries = data.get(section)
        if not isinstance(entries, dict):
            continue

        log.info("  - Normalizing section '%s' (%d entries)", section, len(entries))
        for key, entry in entries.items():
            if not isinstance(entry, dict):
                log.warning(
                    "    • Skipping non-dict entry under '%s[%s]'", section, key
                )
                continue
            _ensure_base_entry_fields(
                entry=entry,
                entry_key=key,
                language=lex_lang,
                default_pos=default_pos,
            )

    # honours: ensure required keys but no BaseLexicalEntry fields
    honours = data.get("honours")
    if isinstance(honours, dict):
        log.info("  - Normalizing section 'honours' (%d entries)", len(honours))
        for key, entry in honours.items():
            if not isinstance(entry, dict):
                log.warning("    • Skipping non-dict honour '%s'", key)
                continue
            if "key" not in entry or not entry["key"]:
                entry["key"] = key
            if "label" not in entry or not entry["label"]:
                # Fallback: use key as label
                entry["label"] = key
            if "extra" not in entry or entry["extra"] is None:
                entry["extra"] = {}

    # name_templates: ensure key
    templates = data.get("name_templates")
    if isinstance(templates, dict):
        log.info(
            "  - Normalizing section 'name_templates' (%d entries)", len(templates)
        )
        for key, entry in templates.items():
            if not isinstance(entry, dict):
                log.warning("    • Skipping non-dict template '%s'", key)
                continue
            if "key" not in entry or not entry["key"]:
                entry["key"] = key


def migrate_file(
    path: str,
    *,
    target_version: str,
    dry_run: bool,
    backup: bool,
) -> bool:
    """
    Migrate a single lexicon JSON file in-place (with optional backup).

    Returns True if the file was modified, False if no change was made.
    """
    log.info("Migrating %s", path)

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            log.error("  ! JSON parse error in %s: %s", path, e)
            return False

    if not isinstance(data, dict):
        log.error("  ! Top-level JSON is not an object in %s", path)
        return False

    original = json.dumps(data, ensure_ascii=False, sort_keys=True)

    # Normalize meta and infer language
    meta = _ensure_meta_block(data, path, target_version)
    lex_lang = meta.get("language")

    # Normalize sections
    _migrate_sections(data, lex_lang, path)

    # Check if anything changed
    migrated = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if migrated == original:
        log.info("  - No changes needed.")
        return False

    if dry_run:
        log.info("  - Changes detected (dry-run; not writing).")
        return True

    # Backup
    if backup:
        backup_path = path + ".bak"
        shutil.copy2(path, backup_path)
        log.info("  - Created backup: %s", backup_path)

    # Write back
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    log.info("  - File updated.")

    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate lexicon JSON files to the current schema."
    )
    parser.add_argument(
        "--file",
        "-f",
        dest="file",
        default=None,
        help="Single lexicon JSON file to migrate.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Migrate all lexicon JSON files under data/lexicon/.",
    )
    parser.add_argument(
        "--target-version",
        "-t",
        dest="target_version",
        default="0.2.0",
        help="Target meta.version to set (default: 0.2.0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write any changes; just report what would be changed.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak backups (ignored in dry-run mode).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    # Initialize logging first
    init_logging()

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Determine file set
    files: List[str] = []
    if args.file:
        files = [os.path.abspath(args.file)]
    elif args.all:
        lex_dir = os.path.join(PROJECT_ROOT, "data", "lexicon")
        pattern = os.path.join(lex_dir, "*.json")
        files = sorted(glob(pattern))
    else:
        parser.print_help()
        sys.exit(1)

    if not files:
        log.error("No lexicon files found to migrate.")
        sys.exit(1)

    modified_count = 0
    for path in files:
        if not os.path.isfile(path):
            log.warning("Skipping non-file path: %s", path)
            continue
        changed = migrate_file(
            path,
            target_version=args.target_version,
            dry_run=args.dry_run,
            backup=not args.no_backup and not args.dry_run,
        )
        if changed:
            modified_count += 1

    if args.dry_run:
        log.info("Dry-run complete. Files that would be modified: %d", modified_count)
    else:
        log.info("Migration complete. Files modified: %d", modified_count)


if __name__ == "__main__":
    main()