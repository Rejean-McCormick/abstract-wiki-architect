# tools/everything_matrix/rgl_scanner.py
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Set

# Canonical + only supported config location
CONFIG_PATH = Path("data/config/everything_matrix_config.json")

# Module filename patterns: GrammarFre.gf, SyntaxEng.gf, CatFr.gf, etc.
# Accept both 2-letter (iso2) and 3-letter (wiki/iso3) suffixes.
_LANG_MODULE_RE = re.compile(r"^(Grammar|Cat|Noun|Nouns|Paradigms|Syntax)([A-Za-z]{2,3})$")

# Folders that should never be treated as "families" even if they contain GF files
_NEVER_FAMILY = {"api"}

SCANNER_VERSION = "rgl_scanner/2.4"

# Allow sibling imports (norm/io_utils live beside this file)
sys.path.append(str(Path(__file__).resolve().parent))

try:
    # io_utils.py (canonical shared IO)
    # [FIX] Import the correct name directly
    from io_utils import read_json, atomic_write_json  # type: ignore
    # norm.py (canonical shared normalization)
    from norm import build_wiki_to_iso2, load_iso_to_wiki  # type: ignore
except Exception as e:
    raise SystemExit(
        "❌ rgl_scanner requires tools/everything_matrix/io_utils.py and norm.py "
        f"(import error: {e})"
    )


def _repo_root() -> Path:
    """
    Resolve repository root robustly, independent of current working directory.

    Anchor rule:
      - Must find data/config/everything_matrix_config.json under repo root.

    Secondary anchor:
      - config/iso_to_wiki.json (useful during refactors if config exists but path probing fails)
    """
    here = Path(__file__).resolve()
    for base in [here.parent, *here.parents]:
        if (base / CONFIG_PATH).is_file():
            return base
        if (base / "config" / "iso_to_wiki.json").is_file():
            return base
    return Path.cwd().resolve()


def _log(msg: str, *, quiet: bool) -> None:
    if not quiet:
        print(msg)


def _load_config(repo: Path) -> Dict[str, Any]:
    """
    Loads the central configuration.

    Clean-mode behavior:
      - Only reads data/config/everything_matrix_config.json.
      - Missing/invalid config => hard fail.

    Supports both shapes inside the canonical file:
      - v2: cfg["rgl"] block
      - v1: top-level keys
    """
    cfg_path = repo / CONFIG_PATH
    cfg = read_json(cfg_path)
    if not isinstance(cfg, dict) or not cfg:
        raise SystemExit(f"❌ Missing/invalid Everything Matrix config: {cfg_path}")

    rgl = cfg.get("rgl") if isinstance(cfg.get("rgl"), dict) else {}

    def pick(key: str, default: Any) -> Any:
        if isinstance(rgl, dict) and key in rgl:
            return rgl.get(key, default)
        return cfg.get(key, default)

    defaults: Dict[str, Any] = {
        "rgl_base_path": "gf-rgl/src",
        "inventory_file": "data/indices/rgl_inventory.json",
        "iso_map_file": "config/iso_to_wiki.json",
        "ignored_folders": ["doc", "docs", "examples", "dist", "bin", "boot", "__pycache__"],
        "include_api_folder": True,
        # Always emit iso2 keys for downstream compatibility
        "inventory_key_mode": "iso2",
    }

    merged: Dict[str, Any] = dict(defaults)
    merged["rgl_base_path"] = pick("rgl_base_path", defaults["rgl_base_path"])
    merged["inventory_file"] = pick("inventory_file", defaults["inventory_file"])
    merged["iso_map_file"] = pick("iso_map_file", defaults["iso_map_file"])
    merged["ignored_folders"] = pick("ignored_folders", defaults["ignored_folders"])
    merged["include_api_folder"] = bool(pick("include_api_folder", defaults["include_api_folder"]))

    ignored = set(str(x) for x in (merged.get("ignored_folders") or []))
    merged["ignored_folders"] = sorted(ignored)

    # Enforce output policy
    merged["inventory_key_mode"] = "iso2"
    return merged


def _build_iso2_to_iso3(iso_to_wiki: Mapping[str, Any]) -> Dict[str, str]:
    """
    Build iso2 -> iso3 preference map from iso_to_wiki.json when possible.
    If multiple iso3 map to the same wiki code, pick the first seen deterministically.
    """
    iso2_to_iso3: Dict[str, str] = {}
    wiki_to_iso3: Dict[str, str] = {}

    for k in sorted(iso_to_wiki.keys(), key=lambda x: str(x).casefold()):
        v = iso_to_wiki.get(k)
        if not (isinstance(k, str) and isinstance(v, Mapping)):
            continue
        kk = k.strip().casefold()
        wiki = v.get("wiki")
        if not (isinstance(wiki, str) and wiki.strip()):
            continue
        wk = wiki.strip().casefold()
        if len(kk) == 3 and wk not in wiki_to_iso3:
            wiki_to_iso3[wk] = kk

    for k, v in iso_to_wiki.items():
        if not (isinstance(k, str) and isinstance(v, Mapping)):
            continue
        kk = k.strip().casefold()
        if len(kk) != 2:
            continue
        wiki = v.get("wiki")
        if not (isinstance(wiki, str) and wiki.strip()):
            continue
        wk = wiki.strip().casefold()
        iso3 = wiki_to_iso3.get(wk)
        if iso3:
            iso2_to_iso3[kk] = iso3

    return iso2_to_iso3


def _resolve_lang_suffix_to_iso2(
    suffix: str,
    *,
    wiki_to_iso2: Mapping[str, str],
    iso_to_wiki: Mapping[str, Any],
    rgl_base: Path = None,  # Added to verify folder existence if needed
) -> Optional[str]:
    """
    Convert GF module suffix into ISO-639-1 (iso2).

    Accepted suffix forms:
      - 2-letter iso2:   "fr", "en" (only if present in iso_to_wiki.json)
      - 3-letter wiki:   "Fre", "Eng" (via wiki_to_iso2)
      - 3-letter iso3:   "fra", "eng" (if present in iso_to_wiki.json, via wiki_to_iso2)

    [FIX 2025-01-01] Strict Fallback Behavior:
      - If strict mapping fails, but the suffix is 3 letters (e.g., 'Hau'),
        we DO NOT blindly accept it. We only accept it if it is a plausible
        RGL code (appears in iso_to_wiki values or known iso3 keys).
      - This prevents garbage like 'Goo' (from SyntaxGoo.gf) from polluting the matrix.
    """
    if not isinstance(suffix, str):
        return None
    s = suffix.strip()
    if len(s) not in (2, 3) or not s.isalpha():
        return None

    key = s.casefold()

    # 1. Try explicit mapping to ISO2 (Wiki Code -> ISO2)
    # e.g. "Fre" -> "fr"
    iso2 = wiki_to_iso2.get(key)
    if isinstance(iso2, str) and len(iso2) == 2:
        return iso2

    # 2. Try explicit 2-letter code in config (ISO2 -> ISO2)
    # e.g. "fr" -> "fr"
    if len(key) == 2 and key in iso_to_wiki:
        return key

    # 3. Try explicit 3-letter code in config (ISO3 -> ISO2 via Wiki map)
    # This handles cases where iso_to_wiki has "zul": {"wiki": "Zul"}
    # If suffix is "zul", we want to map it to "zu" (if it exists) or keep it if standard
    # Since wiki_to_iso2 handles the "wiki" value mapping, we check if key is a known ISO3 key
    if len(key) == 3 and key in iso_to_wiki:
        # If it's a known key in our config, it's valid.
        # We prefer to return a 2-letter code if one is associated with this entry's wiki code
        wiki_val = iso_to_wiki[key].get("wiki", "").lower()
        if wiki_val and wiki_val in wiki_to_iso2:
             return wiki_to_iso2[wiki_val]
        # Otherwise return as is (it's a known 3-letter lang)
        return key

    # 4. [STRICT FIX] 3-letter fallback
    # Only accept unknown 3-letter codes if they look like valid RGL directory names.
    # We avoid blindly returning 'key' here.
    return None


def _compute_blocks_from_modules(modules: Mapping[str, Any]) -> Dict[str, int]:
    """
    Zone A proof-of-existence blocks (0/10).
    Strategy/maturity ladders are applied later by build_index (strategy-map).
    """
    m = set(str(k) for k in (modules.keys() if isinstance(modules, Mapping) else []))
    return {
        "CAT": 10 if "Cat" in m else 0,
        "NOUN": 10 if ("Noun" in m or "Nouns" in m) else 0,
        "PARA": 10 if "Paradigms" in m else 0,
        "GRAM": 10 if "Grammar" in m else 0,
        "SYN": 10 if "Syntax" in m else 0,
    }


def scan_rgl(
    *,
    repo_root: Optional[Path] = None,
    write_output: bool = False,
    output_file: Optional[Path] = None,
    quiet: bool = True,
) -> Dict[str, Any]:
    """
    Library entrypoint (contract):
      scan_rgl(...) -> inventory dict

    Side-effect policy:
      - By default: NO file writes (write_output=False).
      - If write_output=True: write rgl_inventory.json (or output_file if provided).
      - CLI uses this function and decides whether to write.
    """
    repo = repo_root or _repo_root()
    config = _load_config(repo)

    base_path = repo / str(config.get("rgl_base_path", "gf-rgl/src"))
    cfg_out = repo / str(config.get("inventory_file", "data/indices/rgl_inventory.json"))
    out_path = output_file or cfg_out

    iso_map_path = repo / str(config.get("iso_map_file", "config/iso_to_wiki.json"))
    ignored_folders: Set[str] = set(str(x) for x in (config.get("ignored_folders") or []))
    include_api_folder = bool(config.get("include_api_folder", True))

    iso_to_wiki = load_iso_to_wiki(iso_map_path)
    if not iso_to_wiki:
        raise SystemExit(f"❌ Missing/invalid iso_to_wiki.json: {iso_map_path}")

    wiki_to_iso2 = build_wiki_to_iso2(iso_to_wiki)
    iso2_to_iso3 = _build_iso2_to_iso3(iso_to_wiki)

    if not base_path.is_dir():
        raise SystemExit(f"❌ RGL base path not found: {base_path}")

    _log(f"🔍 Scanning {base_path} for RGL modules...", quiet=quiet)

    inventory: Dict[str, Dict[str, Any]] = {}
    family_folders: Set[str] = set()

    for root_dir, dirs, files in os.walk(base_path):
        folder_name = Path(root_dir).name

        # Prune traversal for ignored folders
        dirs[:] = [d for d in dirs if d not in ignored_folders and not d.startswith(".")]

        # Optionally exclude api traversal (but still never classify it as family)
        if not include_api_folder and folder_name == "api":
            dirs[:] = []
            continue

        gf_files = [f for f in files if f.endswith(".gf")]
        if not gf_files:
            continue

        is_language_folder = False

        for file in gf_files:
            name_part = file[:-3]
            m = _LANG_MODULE_RE.match(name_part)
            if not m:
                continue

            module_type, suffix = m.group(1), m.group(2)
            
            # Pass RGL Base to allow folder checking if we wanted to implement deep fallback
            iso2 = _resolve_lang_suffix_to_iso2(
                suffix, wiki_to_iso2=wiki_to_iso2, iso_to_wiki=iso_to_wiki
            )
            
            if not iso2:
                # Last resort heuristic: If the suffix exactly matches the folder name, 
                # and the folder is a known 3-letter code, we might accept it.
                # But to be safe and avoid "Goo", we skip if it didn't resolve.
                continue

            is_language_folder = True

            iso3 = iso2_to_iso3.get(iso2)
            full_path = Path(root_dir) / file
            norm_module_path = full_path.relative_to(repo).as_posix()
            norm_folder_path = Path(root_dir).relative_to(repo).as_posix()

            rec = inventory.setdefault(
                iso2,
                {
                    "path": norm_folder_path,
                    "wiki": suffix,  # observed suffix for debugging
                    "iso2": iso2,
                    "iso3": iso3,
                    "modules": {},
                },
            )
            # Deterministic: keep first discovered path for a module
            rec["modules"].setdefault(module_type, norm_module_path)

        # Family detection: folder with GF files but not a language folder
        if (
            not is_language_folder
            and folder_name not in ignored_folders
            and folder_name not in _NEVER_FAMILY
            and not folder_name.startswith(".")
        ):
            family_folders.add(folder_name)

    # Deterministic output ordering + compute blocks
    final_languages: Dict[str, Any] = {}
    for iso2 in sorted(inventory.keys(), key=lambda x: str(x).casefold()):
        rec = inventory[iso2]
        mods = rec.get("modules", {}) or {}
        rec["modules"] = {k: mods[k] for k in sorted(mods.keys(), key=lambda x: str(x).casefold())}
        rec["blocks"] = _compute_blocks_from_modules(rec["modules"])
        rec["module_count"] = len(rec["modules"])
        rec["completeness"] = round(sum(rec["blocks"].values()) / 50.0, 2)  # 0.0..1.0
        final_languages[iso2] = rec

    final_data: Dict[str, Any] = {
        "meta": {
            "scanner": SCANNER_VERSION,
            "generated_at": int(time.time()),
            "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "inventory_key_mode": "iso2",
            "rgl_base_path": str(base_path.relative_to(repo).as_posix()),
            "iso_map_file": str(iso_map_path.relative_to(repo).as_posix()),
        },
        "stats": {
            "languages_found": len(final_languages),
            "families_found": len(family_folders),
            "full_rgl_5_of_5": sum(
                1
                for r in final_languages.values()
                if isinstance(r.get("blocks"), dict)
                and all((r["blocks"].get(k, 0) == 10) for k in ("CAT", "NOUN", "PARA", "GRAM", "SYN"))
            ),
        },
        "languages": final_languages,
        "families": sorted(family_folders, key=lambda x: str(x).casefold()),
    }

    if write_output:
        # [FIX] Use atomic_write_json directly
        atomic_write_json(out_path, final_data)
        _log(f"✅ Inventory saved to {out_path}", quiet=quiet)
        _log(f"   Languages found: {len(final_languages)}", quiet=quiet)
        _log(f"   Families/Shared folders detected: {len(family_folders)}", quiet=quiet)

    return final_data


def main() -> None:
    """
    Debug CLI:
      - Default: prints JSON to stdout (NO writes).
      - Use --write to persist to configured inventory file (or --output).
    """
    parser = argparse.ArgumentParser(description="Scan gf-rgl/src and produce rgl_inventory.json (debug tool).")
    parser.add_argument("--write", action="store_true", help="Write inventory file to disk")
    parser.add_argument("--output", type=str, default="", help="Override output file path (implies --write)")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output (JSON still printed)")
    args = parser.parse_args()

    repo = _repo_root()
    out_path = Path(args.output) if args.output.strip() else None
    write = bool(args.write or (out_path is not None))

    data = scan_rgl(repo_root=repo, write_output=write, output_file=out_path, quiet=bool(args.quiet))

    # Always print JSON to stdout for debug workflows
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()