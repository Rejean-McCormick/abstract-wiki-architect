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

# Add project root for utils import
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from utils.tool_run_logging import tool_logging

# Allow sibling imports (norm/io_utils live beside this file)
sys.path.append(str(Path(__file__).resolve().parent))

try:
    # io_utils.py (canonical shared IO)
    from io_utils import read_json, atomic_write_json  # type: ignore
    # norm.py (canonical shared normalization)
    from norm import build_wiki_to_iso2, load_iso_to_wiki  # type: ignore
except Exception as e:
    raise SystemExit(
        "❌ rgl_scanner requires tools/everything_matrix/io_utils.py and norm.py "
        f"(import error: {e})"
    )

SCANNER_VERSION = "rgl_scanner/2.4"

# Canonical + only supported config location
CONFIG_PATH = Path("data/config/everything_matrix_config.json")

# Module filename patterns
_LANG_MODULE_RE = re.compile(r"^(Grammar|Cat|Noun|Nouns|Paradigms|Syntax)([A-Za-z]{2,3})$")

# Folders that should never be treated as "families"
_NEVER_FAMILY = {"api"}


def _repo_root() -> Path:
    """Resolve repository root robustly."""
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
    """Loads the central configuration."""
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
    merged["inventory_key_mode"] = "iso2"
    return merged


def _build_iso2_to_iso3(iso_to_wiki: Mapping[str, Any]) -> Dict[str, str]:
    """Build iso2 -> iso3 preference map."""
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
    rgl_base: Path = None,
) -> Optional[str]:
    """Convert GF module suffix into ISO-639-1 (iso2)."""
    if not isinstance(suffix, str):
        return None
    s = suffix.strip()
    if len(s) not in (2, 3) or not s.isalpha():
        return None

    key = s.casefold()

    # 1. Wiki Code -> ISO2
    iso2 = wiki_to_iso2.get(key)
    if isinstance(iso2, str) and len(iso2) == 2:
        return iso2

    # 2. ISO2 -> ISO2
    if len(key) == 2 and key in iso_to_wiki:
        return key

    # 3. ISO3 -> ISO2 via Wiki map
    if len(key) == 3 and key in iso_to_wiki:
        wiki_val = iso_to_wiki[key].get("wiki", "").lower()
        if wiki_val and wiki_val in wiki_to_iso2:
             return wiki_to_iso2[wiki_val]
        return key

    return None


def _compute_blocks_from_modules(modules: Mapping[str, Any]) -> Dict[str, int]:
    """Zone A proof-of-existence blocks (0/10)."""
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
    Library entrypoint: scan_rgl(...) -> inventory dict
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

        # Prune traversal
        dirs[:] = [d for d in dirs if d not in ignored_folders and not d.startswith(".")]

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
            
            iso2 = _resolve_lang_suffix_to_iso2(
                suffix, wiki_to_iso2=wiki_to_iso2, iso_to_wiki=iso_to_wiki
            )
            
            if not iso2:
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
                    "wiki": suffix,
                    "iso2": iso2,
                    "iso3": iso3,
                    "modules": {},
                },
            )
            rec["modules"].setdefault(module_type, norm_module_path)

        if (
            not is_language_folder
            and folder_name not in ignored_folders
            and folder_name not in _NEVER_FAMILY
            and not folder_name.startswith(".")
        ):
            family_folders.add(folder_name)

    # Output assembly
    final_languages: Dict[str, Any] = {}
    for iso2 in sorted(inventory.keys(), key=lambda x: str(x).casefold()):
        rec = inventory[iso2]
        mods = rec.get("modules", {}) or {}
        rec["modules"] = {k: mods[k] for k in sorted(mods.keys(), key=lambda x: str(x).casefold())}
        rec["blocks"] = _compute_blocks_from_modules(rec["modules"])
        rec["module_count"] = len(rec["modules"])
        rec["completeness"] = round(sum(rec["blocks"].values()) / 50.0, 2)
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
        atomic_write_json(out_path, final_data)
        _log(f"✅ Inventory saved to {out_path}", quiet=quiet)
        _log(f"   Languages found: {len(final_languages)}", quiet=quiet)
        _log(f"   Families/Shared folders detected: {len(family_folders)}", quiet=quiet)

    return final_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan gf-rgl/src and produce rgl_inventory.json (debug tool).")
    parser.add_argument("--write", action="store_true", help="Write inventory file to disk")
    parser.add_argument("--output", type=str, default="", help="Override output file path (implies --write)")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output (JSON still printed)")
    args = parser.parse_args()

    with tool_logging("rgl_scanner") as ctx:
        repo = _repo_root()
        out_path = Path(args.output) if args.output.strip() else None
        write = bool(args.write or (out_path is not None))

        ctx.log_stage("Scanning GF-RGL")
        data = scan_rgl(repo_root=repo, write_output=write, output_file=out_path, quiet=bool(args.quiet))

        # Add log summary to meta for JSON consumer
        langs_found = len(data.get("languages", {}))
        families_found = len(data.get("families", []))
        data["meta"]["log_summary"] = f"Found {langs_found} languages, {families_found} families."

        # Always print JSON to stdout
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        ctx.finish({
            "languages": langs_found,
            "families": families_found,
            "written": write
        })


if __name__ == "__main__":
    main()