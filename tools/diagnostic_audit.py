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
# 🕵️ ABSTRACT WIKI DIAGNOSTIC AUDITOR (v3.0, canonical-only)
# ==============================================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT_DIR / "data" / "indices" / "everything_matrix.json"
ISO_MAP_PATH = ROOT_DIR / "data" / "config" / "iso_to_wiki.json"

# Canonical source/output locations only
APP_DIR = ROOT_DIR / "gf"
CONTRIB_DIR = ROOT_DIR / "gf" / "contrib"
RGL_DIR = ROOT_DIR / "gf-rgl" / "src"

SAFE_MODE_DIR = ROOT_DIR / "generated" / "safe_mode" / "src"  # current SAFE_MODE concretes
GENERATED_SRC_DIR = ROOT_DIR / "generated" / "src"            # canonical generated Syntax*.gf

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


def _safe_exists(path: Path) -> Tuple[bool, Optional[str]]:
    try:
        return path.exists(), None
    except OSError as e:
        return False, f"{type(e).__name__}: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _safe_is_dir(path: Path) -> Tuple[bool, Optional[str]]:
    try:
        return path.is_dir(), None
    except OSError as e:
        return False, f"{type(e).__name__}: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _safe_read_text(path: Path) -> Tuple[Optional[str], Optional[str]]:
    try:
        return path.read_text(encoding="utf-8"), None
    except OSError as e:
        return None, f"{type(e).__name__}: {e}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _load_iso_map() -> Dict[str, Any]:
    exists, err = _safe_exists(ISO_MAP_PATH)
    if err or not exists:
        return {}

    text, err = _safe_read_text(ISO_MAP_PATH)
    if err or text is None:
        return {}

    try:
        data = json.loads(text)
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

    return f"Wiki{key.title()}"


def _syntax_module_for(wiki_module: str) -> str:
    """
    WikiEng -> SyntaxEng
    """
    if wiki_module.startswith("Wiki") and len(wiki_module) > 4:
        return f"Syntax{wiki_module[4:]}"
    return "SyntaxUnknown"


def _candidate_paths_for(iso2: str, wiki_module: str) -> Dict[str, List[Path]]:
    """
    Canonical-only candidate file locations.

    - app: canonical app concrete in gf/Wiki*.gf
    - generated: canonical generated outputs only
        * SAFE_MODE concrete: generated/safe_mode/src/Wiki*.gf
        * bridge syntax: generated/src/Syntax*.gf
    - contrib: optional hand-authored/generated contrib override area
    """
    wiki_file = f"{wiki_module}.gf"
    syntax_file = f"{_syntax_module_for(wiki_module)}.gf"

    out: Dict[str, List[Path]] = {
        "app": [
            APP_DIR / wiki_file,
        ],
        "generated": [
            SAFE_MODE_DIR / wiki_file,
            GENERATED_SRC_DIR / syntax_file,
        ],
        "contrib": [
            CONTRIB_DIR / iso2 / wiki_file,
            CONTRIB_DIR / iso2.lower() / wiki_file,
            CONTRIB_DIR / wiki_file,
        ],
    }
    return out


def check_zombie_file(path: Path) -> str:
    """
    Forensics: inspect a .gf file and classify old broken "zombies" vs clean connectors.
    Always resilient to broken/inaccessible paths.
    """
    exists, err = _safe_exists(path)
    if err:
        return f"PATH_ERROR: {err}"
    if not exists:
        return "MISSING"

    content, err = _safe_read_text(path)
    if err or content is None:
        return f"ERROR_READING: {err or 'unknown'}"

    lines = content.splitlines()
    line_count = len(lines)

    # Strong zombie indicators from legacy broken builds (heuristic)
    zombie_markers = ("mkN", "mkAdv", "apple_N")
    if any(m in content for m in zombie_markers) and line_count > 10:
        return "ZOMBIE_OLD_BROKEN"

    # Typical clean one-liners / small generated connectors
    if line_count <= 10:
        if "concrete" in content and "of SemantikArchitect" in content:
            return "CLEAN_APP_CONNECTOR"
        if "instance" in content and "of Syntax" in content:
            return "CLEAN_BRIDGE_CONNECTOR"
        if "open Syntax" in content and "{" in content and "}" in content:
            return "CLEAN_EMPTY_CONNECTOR"
        return "SMALL_UNKNOWN"

    # Typical SAFE_MODE generated concrete
    if (
        "GENERATED_BY_ABSTRACTWIKI_SAFE_MODE" in content
        or ("concrete" in content and "open Prelude" in content and "mkBioProf" in content)
    ):
        return "CLEAN_SAFE_MODE_CONNECTOR"

    if line_count > 50:
        return "SUSPICIOUS_TOO_LARGE"

    return "UNKNOWN_CONTENT"


def _bucket_severity(status: str) -> int:
    """
    Higher is worse.
    """
    if "ZOMBIE" in status:
        return 5
    if "PATH_ERROR" in status:
        return 4
    if "ERROR_READING" in status:
        return 4
    if "SUSPICIOUS" in status:
        return 3
    if status == "UNKNOWN_CONTENT":
        return 2
    if status == "SMALL_UNKNOWN":
        return 1
    if status == "MISSING":
        return 0
    return 0


def run_audit(*, verbose: bool = False, json_output: bool = False) -> int:
    start_time = time.time()
    trace_id = os.environ.get("TOOL_TRACE_ID", "N/A")

    if verbose:
        print(f"START: diagnostic_audit | TraceID: {trace_id}")
        print(f"CWD: {os.getcwd()}")
        print(f"ROOT: {ROOT_DIR}")

    exists, err = _safe_exists(MATRIX_PATH)
    if err:
        payload = {"error": f"Matrix path inaccessible: {err}", "path": str(MATRIX_PATH)}
        print(json.dumps(payload, indent=2) if json_output else payload["error"])
        return 1
    if not exists:
        payload = {"error": "Matrix file not found", "path": str(MATRIX_PATH)}
        print(json.dumps(payload, indent=2) if json_output else payload["error"])
        return 1

    matrix_text, err = _safe_read_text(MATRIX_PATH)
    if err or matrix_text is None:
        payload = {"error": f"Failed to read matrix JSON: {err or 'unknown'}", "path": str(MATRIX_PATH)}
        print(json.dumps(payload, indent=2) if json_output else payload["error"])
        return 1

    try:
        matrix = json.loads(matrix_text)
    except Exception as e:
        payload = {"error": f"Failed to parse matrix JSON: {e}", "path": str(MATRIX_PATH)}
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
    path_errors_found: List[str] = []
    results: List[Dict[str, Any]] = []

    if not json_output:
        print_c("HEADER", "\n🚀 STARTING DEEP SYSTEM AUDIT")
        print_c("HEADER", "===========================")
        print_c("CYAN", f"📊 Matrix Index: {len(langs)} languages found.\n")
        print(f"{'ISO':<6} | {'STRATEGY':<12} | {'APP':<24} | {'GEN':<24} | {'CONTRIB':<24} | {'RGL'}")
        print("-" * 140)

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
        syntax_module = _syntax_module_for(wiki_module)
        candidates = _candidate_paths_for(iso2, wiki_module)

        bucket_details: Dict[str, List[Dict[str, str]]] = {"app": [], "generated": [], "contrib": []}
        bucket_primary: Dict[str, str] = {"app": "MISSING", "generated": "MISSING", "contrib": "MISSING"}

        for bucket in ("app", "generated", "contrib"):
            for p in candidates[bucket]:
                exists, err = _safe_exists(p)

                if err:
                    bucket_details[bucket].append(
                        {"path": str(p), "status": "PATH_ERROR", "error": err}
                    )
                    path_errors_found.append(str(p))
                    continue

                if not exists:
                    continue

                status = check_zombie_file(p)
                entry: Dict[str, str] = {"path": str(p), "status": status}
                bucket_details[bucket].append(entry)

                if "ZOMBIE" in status:
                    zombies_found.append(str(p))
                elif "PATH_ERROR" in status or "ERROR_READING" in status:
                    path_errors_found.append(str(p))
                elif "SUSPICIOUS" in status:
                    suspicious_files.append(str(p))

            if bucket_details[bucket]:
                statuses = [d["status"] for d in bucket_details[bucket]]
                bucket_primary[bucket] = max(statuses, key=_bucket_severity)

        rgl_folder = str(meta.get("folder", "???"))
        rgl_path = RGL_DIR / rgl_folder
        rgl_exists, rgl_err = _safe_exists(rgl_path)

        if not json_output:
            row_color = "RESET"
            if any("ZOMBIE" in bucket_primary[b] for b in bucket_primary):
                row_color = "FAIL"
            elif any(
                ("PATH_ERROR" in bucket_primary[b]) or ("ERROR_READING" in bucket_primary[b]) or ("SUSPICIOUS" in bucket_primary[b])
                for b in bucket_primary
            ):
                row_color = "WARN"

            rgl_label = "Found" if rgl_exists else "Missing"
            if rgl_err:
                rgl_label = f"PathError ({rgl_folder})"

            print_c(
                row_color,
                f"{iso2:<6} | {str(strategy):<12} | {bucket_primary['app']:<24} | {bucket_primary['generated']:<24} | "
                f"{bucket_primary['contrib']:<24} | {rgl_label} ({rgl_folder})",
            )

        result_row: Dict[str, Any] = {
            "iso": iso2,
            "wiki_module": wiki_module,
            "syntax_module": syntax_module,
            "strategy": strategy,
            "app": bucket_details["app"],
            "generated": bucket_details["generated"],
            "contrib": bucket_details["contrib"],
            "rgl": {"folder": rgl_folder, "exists": bool(rgl_exists)},
        }
        if rgl_err:
            result_row["rgl"]["error"] = rgl_err

        results.append(result_row)

    duration = time.time() - start_time

    summary: Dict[str, Any] = {
        "timestamp": time.time(),
        "duration_sec": duration,
        "scanned_languages": len([k for k in langs.keys() if isinstance(k, str) and k.strip()]),
        "zombies_count": len(zombies_found),
        "suspicious_count": len(suspicious_files),
        "path_errors_count": len(path_errors_found),
        "zombie_paths": zombies_found,
        "suspicious_paths": suspicious_files,
        "path_error_paths": path_errors_found,
        "status": (
            "FAIL"
            if zombies_found
            else ("WARN" if suspicious_files or path_errors_found else "OK")
        ),
    }

    if json_output:
        if verbose:
            summary["results"] = results
        print(json.dumps(summary, indent=2))
    else:
        print("\n")
        print_c("HEADER", "🩺 DIAGNOSTIC REPORT")
        print_c("HEADER", "-------------------")

        if zombies_found:
            print_c("FAIL", f"🧟 ZOMBIE FILES DETECTED: {len(zombies_found)}")
            print("    These files look like broken leftovers from previous bad builds.")
            print_c("WARN", "    👉 Suggestion: remove and rebuild generated artifacts.")
            for z in zombies_found:
                print(f"      {z}")
        else:
            print_c("GREEN", "✅ No zombie files detected.")

        if path_errors_found:
            print_c("WARN", f"⚠️  INACCESSIBLE PATHS: {len(path_errors_found)}")
            print("    Some paths could not be inspected safely by the OS/runtime.")
            if verbose:
                for p in path_errors_found:
                    print(f"      {p}")

        if suspicious_files and verbose:
            print_c("WARN", f"⚠️  SUSPICIOUS FILES: {len(suspicious_files)}")
            for s in suspicious_files:
                print(f"      {s}")

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