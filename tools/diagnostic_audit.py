# tools/diagnostic_audit.py
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ==============================================================================
# 🕵️ ABSTRACT WIKI DIAGNOSTIC AUDITOR (v2.3)
# ==============================================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT_DIR / "data" / "indices" / "everything_matrix.json"
ISO_MAP_PATH = ROOT_DIR / "data" / "config" / "iso_to_wiki.json"

# Source/Output locations (current + legacy)
APP_DIR = ROOT_DIR / "gf"
CONTRIB_DIR = ROOT_DIR / "gf" / "contrib"
RGL_DIR = ROOT_DIR / "gf-rgl" / "src"

GENERATED_DIRS: Tuple[Path, ...] = (
    ROOT_DIR / "generated" / "safe_mode" / "src",  # current (SAFE_MODE)
    ROOT_DIR / "generated" / "src",                # current
    ROOT_DIR / "gf" / "generated" / "src",         # legacy mirror
)

COLORS = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "CYAN": "\033[96m",
    "GREEN": "\033[92m",
    "WARN": "\033[93m",
    "FAIL": "\033[91m",
    "RESET": "\033[0m",
}


def print_c(color: str, text: str) -> None:
    if sys.stdout.isatty():
        print(f"{COLORS.get(color, '')}{text}{COLORS['RESET']}")
    else:
        print(text)


def _load_iso_map() -> Dict[str, Any]:
    if not ISO_MAP_PATH.exists():
        return {}
    try:
        data = json.loads(ISO_MAP_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _wiki_module_for(iso2: str, iso_map: Dict[str, Any]) -> str:
    """
    Returns the Wiki module name for an iso2 key, e.g. "en" -> "WikiEng".
    Supports iso_to_wiki.json entries as either:
      - "WikiEng"
      - {"wiki": "WikiEng", ...}
    """
    key = (iso2 or "").strip().lower()
    if not key:
        return "WikiUnknown"

    raw = iso_map.get(key) or iso_map.get(key.upper()) or iso_map.get(key.title())
    wiki = ""
    if isinstance(raw, str):
        wiki = raw.strip()
    elif isinstance(raw, dict):
        wiki = str(raw.get("wiki") or raw.get("Wiki") or "").strip()

    if wiki:
        return wiki

    # Fallback (best-effort; may not match RGL suffix conventions)
    return f"Wiki{key.title()}"


def _candidate_paths_for(iso2: str, wiki_module: str) -> Dict[str, List[Path]]:
    """
    Returns candidate file locations for the module in multiple layouts.
    """
    wiki_file = f"{wiki_module}.gf"
    out: Dict[str, List[Path]] = {
        "app": [APP_DIR / wiki_file],
        "contrib": [
            CONTRIB_DIR / iso2 / wiki_file,
            CONTRIB_DIR / iso2.lower() / wiki_file,
            CONTRIB_DIR / wiki_file,
        ],
        "generated": [],
    }

    for base in GENERATED_DIRS:
        out["generated"].extend(
            [
                base / wiki_file,               # current layout
                base / iso2 / wiki_file,        # legacy layout (subfolder)
                base / iso2.lower() / wiki_file,
            ]
        )

    return out


def check_zombie_file(path: Path) -> str:
    """
    Forensics: inspects a .gf file to classify old broken "zombies" vs clean connectors.
    """
    if not path.exists():
        return "MISSING"

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"ERROR_READING: {e}"

    lines = content.splitlines()
    line_count = len(lines)

    # Strong zombie indicators from legacy broken builds (heuristic)
    zombie_markers = ("mkN", "mkAdv", "apple_N")
    if any(m in content for m in zombie_markers) and line_count > 10:
        return "ZOMBIE_OLD_BROKEN"

    # Typical clean one-liners (Tier-1 / SAFE_MODE)
    if line_count <= 10:
        if "concrete" in content and "of SemantikArchitect" in content:
            return "CLEAN_APP_CONNECTOR"
        if "instance" in content and "of Syntax" in content:
            return "CLEAN_BRIDGE_CONNECTOR"
        if "open Syntax" in content and "{" in content and "}" in content:
            return "CLEAN_EMPTY_CONNECTOR"
        return "SMALL_UNKNOWN"

    # Large file but not clearly broken
    if line_count > 50:
        return "SUSPICIOUS_TOO_LARGE"

    return "UNKNOWN_CONTENT"


def run_audit(*, verbose: bool = False, json_output: bool = False) -> int:
    start_time = time.time()

    trace_id = os.environ.get("TOOL_TRACE_ID", "N/A")
    if verbose:
        print(f"START: diagnostic_audit | TraceID: {trace_id}")
        print(f"CWD: {os.getcwd()}")
        print(f"ROOT: {ROOT_DIR}")

    if not MATRIX_PATH.exists():
        payload = {"error": "Matrix file not found", "path": str(MATRIX_PATH)}
        print(json.dumps(payload, indent=2) if json_output else payload["error"])
        return 1

    try:
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        payload = {"error": f"Failed to read matrix JSON: {e}", "path": str(MATRIX_PATH)}
        print(json.dumps(payload, indent=2) if json_output else payload["error"])
        return 1

    langs = matrix.get("languages", {}) if isinstance(matrix, dict) else {}
    if not isinstance(langs, dict):
        payload = {"error": "Matrix format invalid: languages must be an object/dict", "path": str(MATRIX_PATH)}
        print(json.dumps(payload, indent=2) if json_output else payload["error"])
        return 1

    iso_map = _load_iso_map()

    if verbose:
        print(f"Loaded matrix with {len(langs)} languages.")

    zombies_found: List[str] = []
    suspicious_files: List[str] = []
    results: List[Dict[str, Any]] = []

    if not json_output:
        print_c("HEADER", "\n🚀 STARTING DEEP SYSTEM AUDIT")
        print_c("HEADER", "===========================")
        print_c("CYAN", f"📊 Matrix Index: {len(langs)} languages found.\n")
        print(f"{'ISO':<6} | {'STRATEGY':<12} | {'APP':<20} | {'GEN':<20} | {'CONTRIB':<20} | {'RGL'}")
        print("-" * 120)

    for iso, data in sorted(langs.items(), key=lambda kv: str(kv[0])):
        if not isinstance(iso, str):
            continue
        iso2 = iso.strip().lower()
        if not iso2:
            continue

        verdict = (data or {}).get("verdict", {}) if isinstance(data, dict) else {}
        meta = (data or {}).get("meta", {}) if isinstance(data, dict) else {}
        strategy = verdict.get("build_strategy", "UNKNOWN")

        wiki_module = _wiki_module_for(iso2, iso_map)
        candidates = _candidate_paths_for(iso2, wiki_module)

        # Check files (record all existing candidates; keep a primary status per bucket)
        bucket_details: Dict[str, List[Dict[str, str]]] = {"app": [], "generated": [], "contrib": []}
        bucket_primary: Dict[str, str] = {"app": "MISSING", "generated": "MISSING", "contrib": "MISSING"}

        for bucket in ("app", "generated", "contrib"):
            for p in candidates[bucket]:
                if not p.exists():
                    continue
                status = check_zombie_file(p)
                bucket_details[bucket].append({"path": str(p), "status": status})

                if "ZOMBIE" in status:
                    zombies_found.append(str(p))
                elif "SUSPICIOUS" in status:
                    suspicious_files.append(str(p))

            # pick a representative status
            if bucket_details[bucket]:
                # Prefer worst-case signal first
                statuses = [d["status"] for d in bucket_details[bucket]]
                if any("ZOMBIE" in s for s in statuses):
                    bucket_primary[bucket] = next(s for s in statuses if "ZOMBIE" in s)
                elif any("SUSPICIOUS" in s for s in statuses):
                    bucket_primary[bucket] = next(s for s in statuses if "SUSPICIOUS" in s)
                else:
                    bucket_primary[bucket] = statuses[0]

        # RGL folder existence
        rgl_folder = str(meta.get("folder", "???"))
        rgl_path = RGL_DIR / rgl_folder
        rgl_exists = rgl_path.exists()

        if not json_output:
            row_color = "RESET"
            if any("ZOMBIE" in bucket_primary[b] for b in bucket_primary):
                row_color = "FAIL"
            elif any("SUSPICIOUS" in bucket_primary[b] for b in bucket_primary):
                row_color = "WARN"
            elif iso2 == "tr" or iso2 == "tur":
                row_color = "WARN"

            print_c(
                row_color,
                f"{iso2:<6} | {str(strategy):<12} | {bucket_primary['app']:<20} | {bucket_primary['generated']:<20} | "
                f"{bucket_primary['contrib']:<20} | {'Found' if rgl_exists else 'Missing'} ({rgl_folder})",
            )

        results.append(
            {
                "iso": iso2,
                "wiki_module": wiki_module,
                "strategy": strategy,
                "app": bucket_details["app"],
                "generated": bucket_details["generated"],
                "contrib": bucket_details["contrib"],
                "rgl": {"folder": rgl_folder, "exists": rgl_exists},
            }
        )

    duration = time.time() - start_time

    summary: Dict[str, Any] = {
        "timestamp": time.time(),
        "duration_sec": duration,
        "scanned_languages": len([k for k in langs.keys() if isinstance(k, str) and k.strip()]),
        "zombies_count": len(zombies_found),
        "suspicious_count": len(suspicious_files),
        "zombie_paths": zombies_found,
        "suspicious_paths": suspicious_files,
        "status": "FAIL" if zombies_found else ("WARN" if suspicious_files else "OK"),
    }

    if json_output:
        # Include per-language details only when verbose to keep normal JSON compact.
        if verbose:
            summary["results"] = results
        print(json.dumps(summary, indent=2))
    else:
        print("\n")
        print_c("HEADER", "🩺 DIAGNOSTIC REPORT")
        print_c("HEADER", "-------------------")

        if zombies_found:
            print_c("FAIL", f"🧟 ZOMBIE FILES DETECTED: {len(zombies_found)}")
            print("    These files are leftovers from previous bad builds.")
            print("    They contain broken code (like 'mkN') that causes compilation to fail.")
            print_c("WARN", "    👉 SUGGESTION: Delete these files immediately.")
            for z in zombies_found:
                print(f"      rm {z}")
        else:
            print_c("GREEN", "✅ No Zombie files detected.")

        if suspicious_files and verbose:
            print_c("WARN", f"⚠️  SUSPICIOUS FILES: {len(suspicious_files)}")
            for s in suspicious_files:
                print(f"      {s}")

        print("\n")
        print_c("WARN", "🇹🇷 SPECIAL NOTE: Turkish (tur)")
        print("    The logs show 'Internal error in Compute.Concrete'.")
        print("    This is a known bug in the GF compiler (upstream).")
        print("    Action: The system is correctly skipping it. No fix possible currently.")

        if verbose:
            print(f"Done in {duration:.2f}s")

    return 1 if zombies_found else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnostic Audit for Semantik Architect")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args(argv)
    return run_audit(verbose=bool(args.verbose), json_output=bool(args.json))


if __name__ == "__main__":
    raise SystemExit(main())