# tools/everything_matrix/build_index.py
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Set

# Logging (force so parent processes can't silence it)
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout, force=True)
logger = logging.getLogger(__name__)

# Repo root (tools/everything_matrix/build_index.py -> repo)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Canonical config location (clean; no legacy fallback)
CONFIG_FILE = BASE_DIR / "data" / "config" / "everything_matrix_config.json"

# Sibling imports
sys.path.append(str(Path(__file__).resolve().parent))

from io_utils import atomic_write_json, directory_fingerprint, read_json  # noqa: E402
from norm import (  # noqa: E402
    build_name_map_iso2,
    build_wiki_to_iso2,
    load_iso_to_wiki,
    norm_to_iso2,
)
from zones import (  # noqa: E402
    apply_zone_a_strategy_map,
    clamp10,
    compute_maturity,
    compute_zone_a_from_modules,
    compute_zone_averages,
    normalize_weights,
    choose_build_strategy,
)

# --- Import scanners (libraries; build_index is the orchestrator) ---
try:
    import rgl_scanner  # type: ignore
except Exception:
    rgl_scanner = None  # type: ignore

try:
    import lexicon_scanner  # type: ignore
except Exception:
    lexicon_scanner = None  # type: ignore

try:
    import app_scanner  # type: ignore
except Exception:
    app_scanner = None  # type: ignore

try:
    import qa_scanner  # type: ignore
except Exception:
    qa_scanner = None  # type: ignore


# ---------------------------
# Config normalization (canonical file only, but supports v1 flat keys)
# ---------------------------

def _load_config() -> Dict[str, Any]:
    cfg = read_json(CONFIG_FILE)
    if not isinstance(cfg, dict):
        logger.warning("Config missing/invalid at %s; using defaults.", CONFIG_FILE)
        cfg = {}

    # v2 preferred shape: {rgl:{...}, matrix:{...}, lexicon:{...}, qa:{...}, frontend:{...}, backend:{...}}
    if isinstance(cfg.get("matrix"), dict):
        return cfg

    # v1 flat shape (in canonical location) -> adapt into v2 in-memory
    # NOTE: This is NOT “legacy config file” support; it’s in-file shape migration.
    # logger.warning("Config at %s uses v1 flat shape; adapting to v2 shape in-memory.", CONFIG_FILE)
    out: Dict[str, Any] = dict(cfg)

    out.setdefault("rgl", {})
    out.setdefault("matrix", {})
    out.setdefault("lexicon", {})
    out.setdefault("qa", {})
    out.setdefault("frontend", {})
    out.setdefault("backend", {})

    # RGL
    if isinstance(out["rgl"], dict):
        if "inventory_file" not in out["rgl"] and isinstance(cfg.get("inventory_file"), str):
            out["rgl"]["inventory_file"] = cfg["inventory_file"]

    # MATRIX
    if isinstance(out["matrix"], dict):
        if "everything_index" not in out["matrix"] and isinstance(cfg.get("everything_index"), str):
            out["matrix"]["everything_index"] = cfg["everything_index"]
        if "output_dir" not in out["matrix"] and isinstance(cfg.get("output_dir"), str):
            out["matrix"]["output_dir"] = cfg["output_dir"]
        if "report_dir" not in out["matrix"] and isinstance(cfg.get("report_dir"), str):
            out["matrix"]["report_dir"] = cfg["report_dir"]

    # Frontend block already matches v2 naming in your config snippet
    if isinstance(cfg.get("frontend"), dict) and isinstance(out.get("frontend"), dict):
        out["frontend"] = cfg["frontend"]

    # ISO map stays top-level in both
    if "iso_map_file" not in out and isinstance(cfg.get("iso_map_file"), str):
        out["iso_map_file"] = cfg["iso_map_file"]

    return out


def _paths(repo: Path, cfg: Mapping[str, Any]) -> Dict[str, Path]:
    cfg_matrix = cfg.get("matrix", {}) if isinstance(cfg.get("matrix"), dict) else {}
    cfg_rgl = cfg.get("rgl", {}) if isinstance(cfg.get("rgl"), dict) else {}
    cfg_lex = cfg.get("lexicon", {}) if isinstance(cfg.get("lexicon"), dict) else {}
    cfg_qa = cfg.get("qa", {}) if isinstance(cfg.get("qa"), dict) else {}
    cfg_fe = cfg.get("frontend", {}) if isinstance(cfg.get("frontend"), dict) else {}
    cfg_be = cfg.get("backend", {}) if isinstance(cfg.get("backend"), dict) else {}

    output_dir = repo / str(cfg_matrix.get("output_dir", "data/indices"))
    matrix_file = repo / str(cfg_matrix.get("everything_index", "data/indices/everything_matrix.json"))
    checksum_file = output_dir / "filesystem.checksum"

    rgl_inventory_file = repo / str(cfg_rgl.get("inventory_file", "data/indices/rgl_inventory.json"))
    factory_targets_file = repo / "data" / "config" / "factory_targets.json"

    lex_root = repo / str(cfg_lex.get("lexicon_root", "data/lexicon"))
    gf_root = repo / str(cfg_qa.get("gf_root", "gf"))
    factory_src = gf_root / "generated" / "src"

    flags_dir = repo / str(cfg_fe.get("assets_path", "architect_frontend/public/flags"))
    fe_profiles = repo / str(cfg_fe.get("profiles_path", "architect_frontend/src/config/language_profiles.json"))
    be_profiles = repo / str(cfg_be.get("profiles_path", "app/core/config/profiles/profiles.json"))

    iso_map_file = repo / str(cfg.get("iso_map_file", "config/iso_to_wiki.json"))

    return {
        "output_dir": output_dir,
        "matrix_file": matrix_file,
        "checksum_file": checksum_file,
        "rgl_inventory_file": rgl_inventory_file,
        "factory_targets_file": factory_targets_file,
        "lex_root": lex_root,
        "gf_root": gf_root,
        "factory_src": factory_src,
        "flags_dir": flags_dir,
        "fe_profiles": fe_profiles,
        "be_profiles": be_profiles,
        "iso_map_file": iso_map_file,
    }


# ---------------------------
# Prereq: RGL inventory is an input artifact (regen only if missing or --regen-rgl)
# ---------------------------

def _ensure_rgl_inventory(*, inventory_file: Path, regen: bool) -> Optional[Dict[str, Any]]:
    if (not inventory_file.is_file()) or regen:
        if not rgl_scanner or not hasattr(rgl_scanner, "scan_rgl"):
            logger.warning("RGL inventory missing/regen requested, but rgl_scanner unavailable. Zone A will be zeros.")
            return None
        logger.info("Regenerating RGL inventory via rgl_scanner.scan_rgl()")
        try:
            # [FIX] Force write to disk so subsequent reads find the new data
            rgl_scanner.scan_rgl(write_output=True, output_file=inventory_file)  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning("rgl_scanner.scan_rgl() failed: %s", e)

    inv = read_json(inventory_file)
    return inv if isinstance(inv, dict) else None


def _normalize_inventory_by_iso2(
    languages_obj: Any,
    *,
    wiki_to_iso2: Mapping[str, str],
) -> Dict[str, Dict[str, Any]]:
    """
    Accepts rgl_inventory["languages"] which may be keyed by iso2 already (preferred).
    Best-effort normalization: raw_key -> iso2 via norm_to_iso2().
    """
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(languages_obj, Mapping):
        return out

    for raw_key, rec in languages_obj.items():
        iso2 = norm_to_iso2(str(raw_key), wiki_to_iso2=wiki_to_iso2)
        if not iso2 or iso2 in out:
            continue
        if isinstance(rec, Mapping):
            out[iso2] = dict(rec)
    return out


def _load_factory_targets(path: Path, *, wiki_to_iso2: Mapping[str, str]) -> Dict[str, Any]:
    obj = read_json(path)
    if not isinstance(obj, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in obj.items():
        iso2 = norm_to_iso2(str(k), wiki_to_iso2=wiki_to_iso2)
        if iso2 and iso2 not in out:
            out[iso2] = v
    return out


# ---------------------------
# One-shot scanners (contracts only; no per-iso rescans here)
# ---------------------------

def _scan_all_lexicons(lex_root: Path) -> Dict[str, Dict[str, float]]:
    zeros = {"SEED": 0.0, "CONC": 0.0, "WIDE": 0.0, "SEM": 0.0}
    if not lexicon_scanner or not hasattr(lexicon_scanner, "scan_all_lexicons"):
        logger.warning("lexicon_scanner.scan_all_lexicons missing; Zone B will be zeros.")
        return {}
    try:
        out = lexicon_scanner.scan_all_lexicons(lex_root)  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning("lexicon_scanner.scan_all_lexicons failed; Zone B will be zeros. (%s)", e)
        return {}
    if not isinstance(out, dict):
        return {}
    normed: Dict[str, Dict[str, float]] = {}
    for iso2, blk in out.items():
        if isinstance(iso2, str) and isinstance(blk, Mapping):
            k = iso2.strip().casefold()
            normed[k] = {kk: float(clamp10(blk.get(kk, 0.0))) for kk in zeros}
    return normed


def _scan_all_apps(repo_root: Path) -> Dict[str, Dict[str, float]]:
    zeros = {"PROF": 0.0, "ASST": 0.0, "ROUT": 0.0}
    if not app_scanner or not hasattr(app_scanner, "scan_all_apps"):
        logger.warning("app_scanner.scan_all_apps missing; Zone C will be zeros.")
        return {}
    try:
        out = app_scanner.scan_all_apps(repo_root)  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning("app_scanner.scan_all_apps failed; Zone C will be zeros. (%s)", e)
        return {}
    if not isinstance(out, dict):
        return {}
    normed: Dict[str, Dict[str, float]] = {}
    for iso2, blk in out.items():
        if isinstance(iso2, str) and isinstance(blk, Mapping):
            k = iso2.strip().casefold()
            normed[k] = {kk: float(clamp10(blk.get(kk, 0.0))) for kk in zeros}
    return normed


def _scan_all_artifacts(gf_root: Path) -> Dict[str, Dict[str, float]]:
    zeros = {"BIN": 0.0, "TEST": 0.0}
    if not qa_scanner or not hasattr(qa_scanner, "scan_all_artifacts"):
        logger.warning("qa_scanner.scan_all_artifacts missing; Zone D will be zeros.")
        return {}
    try:
        out = qa_scanner.scan_all_artifacts(gf_root)  # type: ignore[attr-defined]
    except Exception as e:
        logger.warning("qa_scanner.scan_all_artifacts failed; Zone D will be zeros. (%s)", e)
        return {}
    if not isinstance(out, dict):
        return {}
    normed: Dict[str, Dict[str, float]] = {}
    for iso2, blk in out.items():
        if isinstance(iso2, str) and isinstance(blk, Mapping):
            k = iso2.strip().casefold()
            normed[k] = {
                "BIN": float(clamp10(blk.get("BIN", 0.0))),
                "TEST": float(clamp10(blk.get("TEST", 0.0))),
            }
    return normed


# ---------------------------
# Orchestrator
# ---------------------------

def scan_system() -> None:
    parser = argparse.ArgumentParser(description="Build the Everything Matrix index (single orchestrator).")
    parser.add_argument("--force", action="store_true", help="Ignore cache and force rebuild")
    parser.add_argument("--touch-timestamp", action="store_true", help="Rewrite timestamp on cache hit")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")

    # explicit regeneration flags
    parser.add_argument("--regen-rgl", action="store_true", help="Regenerate data/indices/rgl_inventory.json")
    parser.add_argument("--regen-lex", action="store_true", help="Force Zone B rescan")
    parser.add_argument("--regen-app", action="store_true", help="Force Zone C rescan")
    parser.add_argument("--regen-qa", action="store_true", help="Force Zone D rescan")

    args, _ = parser.parse_known_args()
    if args.regen_rgl or args.regen_lex or args.regen_app or args.regen_qa:
        args.force = True

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # HEADER
    logger.info("=== EVERYTHING MATRIX ORCHESTRATOR ===")
    logger.info(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"CWD: {Path.cwd()}")

    cfg = _load_config()
    # Check if v1 adapted or v2 native
    raw_cfg = read_json(CONFIG_FILE)
    is_v1 = isinstance(raw_cfg, dict) and "rgl" not in raw_cfg
    logger.info(f"Config: {CONFIG_FILE} (Detected: {'v1-flat' if is_v1 else 'v2-nested'})")

    p = _paths(BASE_DIR, cfg)

    cfg_matrix = cfg.get("matrix", {}) if isinstance(cfg.get("matrix"), dict) else {}
    scoring_version = str(cfg_matrix.get("scoring_version", "2.4"))

    # normalization inputs
    iso_to_wiki = load_iso_to_wiki(p["iso_map_file"])
    wiki_to_iso2 = build_wiki_to_iso2(iso_to_wiki)
    name_map_iso2 = build_name_map_iso2(iso_to_wiki, wiki_to_iso2)

    # fingerprint inputs (what we read/scan on a normal run)
    content_roots = [p["lex_root"], p["factory_src"], p["gf_root"], p["flags_dir"]]
    config_files = [
        CONFIG_FILE,
        p["iso_map_file"],
        p["rgl_inventory_file"],
        p["factory_targets_file"],
        p["fe_profiles"],
        p["be_profiles"],
        Path(__file__),
    ]

    p["output_dir"].mkdir(parents=True, exist_ok=True)
    
    # Fingerprint check
    current_fp = directory_fingerprint(content_roots=content_roots, config_files=config_files)
    logger.debug(f"Calculated Fingerprint: {current_fp[:12]}...")

    # cache check
    if (not args.force) and p["checksum_file"].is_file() and p["matrix_file"].is_file():
        stored = p["checksum_file"].read_text(encoding="utf-8").strip()
        if stored == current_fp:
            if args.touch_timestamp:
                matrix = read_json(p["matrix_file"]) or {}
                if isinstance(matrix, dict):
                    ts = time.time()
                    matrix["timestamp"] = ts
                    matrix["timestamp_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
                    atomic_write_json(p["matrix_file"], matrix)
                    logger.info("✅ Cache HIT. Inputs unchanged. Timestamp refreshed.")
                else:
                    logger.info("✅ Cache HIT. Inputs unchanged. Matrix unreadable; skipping refresh.")
            else:
                logger.info("✅ Cache HIT. Inputs unchanged.")
            return
        else:
            logger.info(f"♻️  Cache MISS. Stored: {stored[:12]}... != Current: {current_fp[:12]}...")
    else:
        if args.force:
            logger.info("🔨 Force rebuild requested.")

    logger.info("Everything Matrix build starting (scoring_version=%s).", scoring_version)

    # 1) Zone A source: rgl_inventory.json (regen only if missing or --regen-rgl)
    rgl_inventory = _ensure_rgl_inventory(inventory_file=p["rgl_inventory_file"], regen=bool(args.regen_rgl))
    rgl_by_iso2: Dict[str, Dict[str, Any]] = {}
    if isinstance(rgl_inventory, dict):
        rgl_by_iso2 = _normalize_inventory_by_iso2(rgl_inventory.get("languages"), wiki_to_iso2=wiki_to_iso2)

    # 2) Factory targets registry (iso2)
    factory_registry = _load_factory_targets(p["factory_targets_file"], wiki_to_iso2=wiki_to_iso2)

    # 3) One-shot scans per zone (no per-iso rescans here)
    logger.info("--- Phase 1: One-Shot Scans ---")
    
    logger.info("Calling lexicon_scanner...")
    lex_inv = _scan_all_lexicons(p["lex_root"])
    logger.info(f"  -> Lexicon inventory: {len(lex_inv)} languages.")

    logger.info("Calling app_scanner...")
    app_inv = _scan_all_apps(BASE_DIR)
    logger.info(f"  -> App inventory: {len(app_inv)} languages.")
    
    logger.info("Calling qa_scanner...")
    qa_inv = _scan_all_artifacts(p["gf_root"])
    logger.info(f"  -> QA inventory: {len(qa_inv)} languages.")

    # 4) Build universe (iso2)
    all_isos: Set[str] = set()
    all_isos.update(rgl_by_iso2.keys())
    all_isos.update(factory_registry.keys())
    all_isos.update(lex_inv.keys())
    all_isos.update(app_inv.keys())
    all_isos.update(qa_inv.keys())

    if p["factory_src"].is_dir():
        for d in p["factory_src"].iterdir():
            if d.is_dir():
                iso2 = norm_to_iso2(d.name, wiki_to_iso2=wiki_to_iso2)
                if iso2:
                    all_isos.add(iso2)

    if p["lex_root"].is_dir():
        for d in p["lex_root"].iterdir():
            if d.is_dir():
                iso2 = norm_to_iso2(d.name, wiki_to_iso2=wiki_to_iso2)
                if iso2:
                    all_isos.add(iso2)

    # 5) scoring config
    zone_weights_cfg = cfg_matrix.get("zone_weights", {}) if isinstance(cfg_matrix.get("zone_weights"), dict) else {}
    default_weights = {"A_RGL": 0.40, "B_LEX": 0.35, "C_APP": 0.15, "D_QA": 0.10}
    zone_weights = {**default_weights, **zone_weights_cfg}

    # 6) assemble matrix
    logger.info("--- Phase 2: Synthesis & Scoring ---")
    matrix_langs: Dict[str, Any] = {}

    zeros_b = {"SEED": 0.0, "CONC": 0.0, "WIDE": 0.0, "SEM": 0.0}
    zeros_c = {"PROF": 0.0, "ASST": 0.0, "ROUT": 0.0}
    zeros_d = {"BIN": 0.0, "TEST": 0.0}

    # Tracking skips for summary
    skip_counts: Dict[str, int] = {}
    MAX_VERBOSE_SKIPS = 5  # limit how many we print per reason

    for iso2 in sorted(all_isos):
        if not iso2 or iso2 == "api":
            continue

        # meta
        tier = 3
        origin = "factory"
        folder = "generated"

        rgl_rec = rgl_by_iso2.get(iso2)
        if isinstance(rgl_rec, Mapping):
            tier = 1
            origin = "rgl"
            rgl_path = rgl_rec.get("path")
            folder = Path(rgl_path).name if isinstance(rgl_path, str) and rgl_path.strip() else "rgl"
        elif (p["lex_root"] / iso2).is_dir():
            origin = "lexicon"
            folder = ""

        # Zone A (proof via modules in rgl_inventory.json)
        zone_a_raw = {"CAT": 0.0, "NOUN": 0.0, "PARA": 0.0, "GRAM": 0.0, "SYN": 0.0}
        if isinstance(rgl_rec, Mapping) and isinstance(rgl_rec.get("modules"), Mapping):
            zone_a_raw = compute_zone_a_from_modules(rgl_rec["modules"])  # type: ignore[arg-type]

        # Zone B/C/D from inventories
        zone_b = dict(lex_inv.get(iso2, zeros_b))
        zone_c = dict(app_inv.get(iso2, zeros_c))
        zone_d = dict(qa_inv.get(iso2, zeros_d))

        # pass1
        avgs_1 = compute_zone_averages(zone_a_raw, zone_b, zone_c, zone_d)
        maturity_1 = compute_maturity(avgs_1, zone_weights)
        strat_1 = choose_build_strategy(
            iso2=iso2,
            maturity_score=maturity_1,
            zone_a=zone_a_raw,
            zone_b=zone_b,
            zone_d=zone_d,
            factory_registry=factory_registry,
            cfg_matrix=cfg_matrix,
        )

        # ladder + pass2
        zone_a = apply_zone_a_strategy_map(zone_a_raw, strat_1)
        avgs_2 = compute_zone_averages(zone_a, zone_b, zone_c, zone_d)
        maturity_2 = compute_maturity(avgs_2, zone_weights)
        strat_2 = choose_build_strategy(
            iso2=iso2,
            maturity_score=maturity_2,
            zone_a=zone_a,
            zone_b=zone_b,
            zone_d=zone_d,
            factory_registry=factory_registry,
            cfg_matrix=cfg_matrix,
        )

        runnable = (float(zone_b.get("SEED", 0.0)) >= 2.0) or (strat_2 == "HIGH_ROAD")

        if args.verbose and strat_2 == "SKIP":
            # Simple heuristic reasoning for debug logs
            reason = "low_maturity"
            if float(zone_a_raw.get("CAT", 0)) == 0 and float(zone_b.get("SEED", 0)) == 0:
                reason = "empty_lang"
            elif avgs_1["A_RGL"] < 2.0 and not (iso2 in factory_registry):
                reason = "low_rgl_no_factory"
            
            skip_counts[reason] = skip_counts.get(reason, 0) + 1
            if skip_counts[reason] <= MAX_VERBOSE_SKIPS:
                logger.debug(f"Skipping {iso2}: {reason} (Mat: {maturity_2:.1f})")

        matrix_langs[iso2] = {
            "meta": {
                "iso": iso2,
                "name": name_map_iso2.get(iso2, iso2.upper()),
                "tier": tier,
                "origin": origin,
                "folder": folder,
            },
            "zones": {
                "A_RGL": {k: float(clamp10(v)) for k, v in zone_a.items()},
                "B_LEX": {k: float(clamp10(v)) for k, v in zone_b.items()},
                "C_APP": {k: float(clamp10(v)) for k, v in zone_c.items()},
                "D_QA": {k: float(clamp10(v)) for k, v in zone_d.items()},
            },
            "verdict": {
                "scoring_version": scoring_version,
                "zone_weights": normalize_weights(zone_weights, ("A_RGL", "B_LEX", "C_APP", "D_QA")),
                "zone_averages": avgs_2,
                "maturity_score": maturity_2,
                "build_strategy": strat_2,
                "runnable": bool(runnable),
            },
        }

    # 7) save
    ts = time.time()
    matrix = {
        "timestamp": ts,
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
        "scoring_version": scoring_version,
        "stats": {
            "total_languages": len(matrix_langs),
            "production_ready": sum(
                1
                for l in matrix_langs.values()
                if l["verdict"]["maturity_score"] >= 8.0 and l["verdict"]["build_strategy"] == "HIGH_ROAD"
            ),
            "high_road": sum(1 for l in matrix_langs.values() if l["verdict"]["build_strategy"] == "HIGH_ROAD"),
            "safe_mode": sum(1 for l in matrix_langs.values() if l["verdict"]["build_strategy"] == "SAFE_MODE"),
            "skipped": sum(1 for l in matrix_langs.values() if l["verdict"]["build_strategy"] == "SKIP"),
            "runnable": sum(1 for l in matrix_langs.values() if bool(l["verdict"]["runnable"])),
        },
        "languages": matrix_langs,
    }

    atomic_write_json(p["matrix_file"], matrix)
    p["checksum_file"].write_text(current_fp, encoding="utf-8")

    logger.info("--- Build Summary ---")
    logger.info(f"Total Languages:  {matrix['stats']['total_languages']}")
    logger.info(f"Production Ready: {matrix['stats']['production_ready']}")
    logger.info(f"Build Strategies: HIGH_ROAD={matrix['stats']['high_road']}, SAFE_MODE={matrix['stats']['safe_mode']}, SKIP={matrix['stats']['skipped']}")
    
    # Show top skip reasons if we collected any
    if args.verbose and skip_counts:
        logger.debug("Top Skip Reasons:")
        for r, c in sorted(skip_counts.items(), key=lambda x: x[1], reverse=True):
            logger.debug(f"  {r}: {c}")

    logger.info(f"💾 Written to: {p['matrix_file']}")
    try:
        size = p['matrix_file'].stat().st_size
        logger.info(f"   Size: {size} bytes")
    except Exception:
        pass


if __name__ == "__main__":
    scan_system()