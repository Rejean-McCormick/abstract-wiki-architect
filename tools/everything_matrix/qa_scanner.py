# tools/everything_matrix/qa_scanner.py
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Optional, Set, List

# Robust import for norm.py
try:
    from .norm import load_iso_to_wiki, norm_to_iso2
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parent))
    from norm import load_iso_to_wiki, norm_to_iso2

try:
    import pgf  # type: ignore
except ImportError:
    pgf = None

logger = logging.getLogger(__name__)

SCANNER_VERSION = "qa_scanner/3.1"

# ---- Maturity scoring (0-10) ----
ABSENT = 0
PLANNED = 1
SCAFFOLDED = 3
DRAFT = 5
BETA = 7
PRE_FINAL = 8
FINAL = 10

# --- GLOBAL CACHE ---
_CACHED_GRAMMAR: Any = None
_CACHED_PGF_PATH: Optional[Path] = None
_DIAGNOSTICS: List[str] = []

# -------------------------
# Path resolution
# -------------------------
def _resolve_repo_root_from_gf(gf_root: Path) -> Path:
    gf_root = gf_root.resolve()
    # Expected: <repo>/gf
    if gf_root.name == "gf":
        return gf_root.parent
    # If someone passed repo root by mistake, try to recover
    if (gf_root / "gf").is_dir():
        return gf_root
    return gf_root.parent

def _resolve_iso_map_path(repo_root: Path) -> Path:
    env_override = os.getenv("AWA_ISO_TO_WIKI", "").strip()
    if env_override:
        return Path(env_override)
    return repo_root / "data" / "config" / "iso_to_wiki.json"

def _resolve_junit_path(repo_root: Path) -> Path:
    env_override = os.getenv("AWA_JUNIT_XML", "").strip()
    if env_override:
        return Path(env_override)
    return repo_root / "data" / "tests" / "reports" / "junit.xml"

# -------------------------
# PGF loading (singleton)
# -------------------------
def load_grammar_once(pgf_path: Path):
    global _CACHED_GRAMMAR, _CACHED_PGF_PATH

    if _CACHED_GRAMMAR is not None and _CACHED_PGF_PATH == pgf_path:
        return _CACHED_GRAMMAR

    if not pgf:
        _DIAGNOSTICS.append("PGF library not installed/importable")
        _CACHED_GRAMMAR = None
        _CACHED_PGF_PATH = pgf_path
        return None

    if pgf_path.is_file():
        try:
            logger.info(f"Loading grammar from {pgf_path}")
            _CACHED_GRAMMAR = pgf.readPGF(str(pgf_path))
            _CACHED_PGF_PATH = pgf_path
            return _CACHED_GRAMMAR
        except Exception as e:
            msg = f"Failed to load PGF at {pgf_path}: {e}"
            logger.error(msg)
            _DIAGNOSTICS.append(msg)
            _CACHED_GRAMMAR = None
            _CACHED_PGF_PATH = pgf_path
            return None

    msg = f"PGF file not found at {pgf_path}"
    logger.warning(msg)
    _DIAGNOSTICS.append(msg)
    _CACHED_GRAMMAR = None
    _CACHED_PGF_PATH = pgf_path
    return None

# -------------------------
# JUnit parsing
# -------------------------
_LANG_TOKEN_RE_TEMPLATE = r"(^|[^a-z0-9]){tok}([^a-z0-9]|$)"

def _compile_lang_matchers(iso2: str) -> Set[re.Pattern]:
    tok = (iso2 or "").strip().casefold()
    matchers: Set[re.Pattern] = set()
    if not tok:
        return matchers

    patterns = [
        rf"_{re.escape(tok)}(\b|[^a-z0-9])",
        rf"-{re.escape(tok)}(\b|[^a-z0-9])",
        rf"\[{re.escape(tok)}\]",
        rf"\({re.escape(tok)}\)",
        rf"lang\s*=\s*{re.escape(tok)}(\b|[^a-z0-9])",
        rf"language\s*=\s*{re.escape(tok)}(\b|[^a-z0-9])",
        _LANG_TOKEN_RE_TEMPLATE.format(tok=re.escape(tok)),
    ]
    for p in patterns:
        matchers.add(re.compile(p, re.IGNORECASE))
    return matchers

def _testcase_text(testcase: ET.Element) -> str:
    parts = [
        testcase.get("name", "") or "",
        testcase.get("classname", "") or "",
        testcase.get("file", "") or "",
    ]
    return " ".join(parts).lower()

def _is_failure(testcase: ET.Element) -> bool:
    return testcase.find("failure") is not None or testcase.find("error") is not None

def _is_skipped(testcase: ET.Element) -> bool:
    return testcase.find("skipped") is not None

def _parse_junit_report_pass_rates(path: Path, *, iso2s: Set[str]) -> Dict[str, float]:
    rates: Dict[str, float] = {k: 0.0 for k in iso2s}

    if not iso2s:
        return rates

    if not path.is_file():
        msg = f"JUnit report not found at {path}"
        logger.warning(msg)
        _DIAGNOSTICS.append(msg)
        return rates

    logger.info(f"Parsing JUnit report: {path}")

    try:
        tree = ET.parse(path)
        root = tree.getroot()

        matchers_by_iso2: Dict[str, Set[re.Pattern]] = {
            iso2: _compile_lang_matchers(iso2) for iso2 in iso2s
        }

        totals: Dict[str, int] = {k: 0 for k in iso2s}
        passed: Dict[str, int] = {k: 0 for k in iso2s}

        case_count = 0
        for testcase in root.iter("testcase"):
            case_count += 1
            text = _testcase_text(testcase)
            if _is_skipped(testcase):
                continue

            hit_any = False
            for iso2, matchers in matchers_by_iso2.items():
                if not matchers:
                    continue
                if any(m.search(text) for m in matchers):
                    hit_any = True
                    totals[iso2] += 1
                    if not _is_failure(testcase):
                        passed[iso2] += 1
            if not hit_any:
                continue

        logger.info(f"Parsed {case_count} test cases.")

        for iso2 in iso2s:
            t = totals.get(iso2, 0)
            rates[iso2] = 0.0 if t <= 0 else round(passed.get(iso2, 0) / t, 4)

        return rates

    except Exception as e:
        msg = f"Failed to parse JUnit XML: {e}"
        logger.error(msg)
        _DIAGNOSTICS.append(msg)
        return rates

# -------------------------
# Scanner Logic
# -------------------------
def scan_all_artifacts(
    gf_root: Path,
    *,
    iso_map_path: Optional[Path] = None,
    junit_path: Optional[Path] = None,
) -> Dict[str, Dict[str, float]]:
    # Clear diagnostics for this run
    _DIAGNOSTICS.clear()

    out: Dict[str, Dict[str, float]] = {}
    if not isinstance(gf_root, Path):
        return out

    gf_root = gf_root.resolve()
    repo_root = _resolve_repo_root_from_gf(gf_root)

    logger.info(f"Scanning artifacts in: {repo_root}")

    # 1) ISO map (FIXED): pass a FILE PATH into load_iso_to_wiki()
    iso_map_file = (iso_map_path or _resolve_iso_map_path(repo_root)).resolve()

    if not iso_map_file.is_file():
        msg = f"ISO map not found at {iso_map_file}"
        logger.warning(msg)
        _DIAGNOSTICS.append(msg)
        iso_map: Dict[str, Any] = {}
    else:
        iso_map = load_iso_to_wiki(iso_map_file)

    iso2s: Set[str] = set(iso_map.keys())
    logger.info(f"Loaded ISO map with {len(iso2s)} languages (path={iso_map_file})")

    if not iso2s:
        _DIAGNOSTICS.append(
            f"ISO map loaded 0 languages. Verify file content/format: {iso_map_file}"
        )

    # 2) PGF presence / binary scoring
    pgf_path = gf_root / "AbstractWiki.pgf"
    grammar = load_grammar_once(pgf_path)
    bin_by_iso2: Dict[str, float] = {k: 0.0 for k in iso2s}

    if grammar:
        try:
            langs = getattr(grammar, "languages", None)
            if isinstance(langs, dict):
                lang_keys = list(langs.keys())
                logger.info(f"Found {len(lang_keys)} concrete languages in PGF")
                for iso2 in iso2s:
                    # Check for WikiFr, WikiFR, etc.
                    target1 = f"Wiki{iso2.capitalize()}"
                    target2 = f"Wiki{iso2.upper()}"
                    if target1 in langs or target2 in langs:
                        bin_by_iso2[iso2] = 10.0
                        continue
                    # Suffix check (fallback)
                    for key in lang_keys:
                        sk = str(key)
                        if sk.endswith(iso2.capitalize()) or sk.endswith(iso2.upper()):
                            bin_by_iso2[iso2] = 10.0
                            break
        except Exception as e:
            _DIAGNOSTICS.append(f"Error checking PGF languages: {e}")
    else:
        logger.warning("No grammar loaded, binary scores will be 0.")

    # 3) Test results (JUnit)
    junit_file = (junit_path or _resolve_junit_path(repo_root)).resolve()
    pass_rates = _parse_junit_report_pass_rates(junit_file, iso2s=iso2s)

    for iso2 in sorted(iso2s):
        out[iso2] = {
            "BIN": bin_by_iso2.get(iso2, 0.0),
            "TEST": round(float(pass_rates.get(iso2, 0.0)) * 10.0, 1),
        }

    return out

def _build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="QA scanner for Everything Matrix (BIN + TEST scores).")
    p.add_argument("--gf-root", type=str, default="", help="Path to gf/ directory (default: <repo>/gf).")
    p.add_argument("--repo-root", type=str, default="", help="Repo root override (default: inferred from gf-root).")
    p.add_argument("--iso-map", type=str, default="", help="iso_to_wiki.json override (default: data/config/iso_to_wiki.json).")
    p.add_argument("--junit", type=str, default="", help="JUnit XML override (default: data/tests/reports/junit.xml).")
    p.add_argument("--json-only", action="store_true", help="Print only JSON result (no summary/header).")
    p.add_argument("--verbose", action="store_true", help="Enable more detailed logging.")
    return p

if __name__ == "__main__":
    args = _build_cli().parse_args()

    # Configure stdout logging for GUI
    level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout, force=True)

    start_time = time.time()

    # Resolve roots
    here = Path(__file__).resolve()
    default_repo = here.parents[2]
    repo_root = Path(args.repo_root).resolve() if args.repo_root else default_repo
    gf_root = Path(args.gf_root).resolve() if args.gf_root else (repo_root / "gf")

    iso_map_path = Path(args.iso_map).resolve() if args.iso_map else None
    junit_path = Path(args.junit).resolve() if args.junit else None

    if not args.json_only:
        print(f"=== QA SCANNER ({SCANNER_VERSION}) ===")
        print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
        print(f"Repo Root: {repo_root}")
        print(f"GF Root:   {gf_root}")
        if iso_map_path:
            print(f"ISO Map:   {iso_map_path}")
        if junit_path:
            print(f"JUnit:     {junit_path}")
        print("-" * 40)

    results = scan_all_artifacts(
        gf_root,
        iso_map_path=iso_map_path,
        junit_path=junit_path,
    )

    duration_ms = round((time.time() - start_time) * 1000, 2)

    output = {
        "meta": {
            "scanner": SCANNER_VERSION,
            "repo_root": str(repo_root),
            "gf_root": str(gf_root),
            "iso_map_path": str((iso_map_path or _resolve_iso_map_path(_resolve_repo_root_from_gf(gf_root))).resolve()),
            "junit_path": str((junit_path or _resolve_junit_path(_resolve_repo_root_from_gf(gf_root))).resolve()),
            "duration_ms": duration_ms,
            "diagnostic_count": len(_DIAGNOSTICS),
        },
        "diagnostics": _DIAGNOSTICS[:50],
        "languages": results,
    }

    if not args.json_only:
        print("\n--- Summary ---")
        print(f"Languages Scanned: {len(results)}")
        print(f"Duration:          {duration_ms}ms")
        print(f"Diagnostics:       {len(_DIAGNOSTICS)}")
        if _DIAGNOSTICS:
            print("\n[Diagnostics]")
            for d in _DIAGNOSTICS[:50]:
                print(f" - {d}")

        print("\n--- JSON Result ---")

    print(json.dumps(output, indent=2))
