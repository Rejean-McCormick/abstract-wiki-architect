# tools/everything_matrix/app_scanner.py
from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

# Add project root for utils import
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from utils.tool_run_logging import tool_logging

logger = logging.getLogger(__name__)

SCANNER_VERSION = "app_scanner/2.2"

# Canonical + only supported config path (no legacy fallbacks)
CONFIG_PATH = Path("data/config/everything_matrix_config.json")

# ---- Maturity ladder (0–10) ----
ABSENT = 0
PLANNED = 1
SCAFFOLDED = 3
DRAFT = 5
BETA = 7
PRE_FINAL = 8
FINAL = 10


def _project_root() -> Path:
    """
    Resolve repository root robustly.

    Anchor rule:
      - Must find data/config/everything_matrix_config.json

    Secondary anchor (for IDE/CWD edge cases):
      - config/iso_to_wiki.json

    No legacy config paths are supported.
    """
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / CONFIG_PATH).is_file():
            return p
        if (p / "config" / "iso_to_wiki.json").is_file():
            # In case config exists but is not discovered due to filesystem quirks,
            # still allow root detection by iso map anchor.
            return p
    # Last resort: keep behavior predictable
    return here.parents[2]


def _read_json(path: Path) -> Optional[Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning("Failed to read JSON at %s: %s", path, e)
        return None


def load_config() -> Dict[str, Any]:
    """
    Loads the central Everything Matrix configuration.

    Clean-mode behavior:
      - No legacy fallbacks.
      - Missing/invalid config => hard fail.
    """
    repo = _project_root()
    cfg_path = repo / CONFIG_PATH
    cfg = _read_json(cfg_path)
    if isinstance(cfg, dict):
        return cfg
    raise SystemExit(f"❌ Missing/invalid Everything Matrix config: {cfg_path}")


def _load_iso_to_wiki_map(cfg: Mapping[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Loads config/iso_to_wiki.json which maps ISO codes -> {wiki, name}.

    Keys may include 2-letter and 3-letter variants.
    Clean-mode behavior:
      - Missing/invalid iso map => hard fail (do not invent).
    """
    repo = _project_root()
    iso_map_rel = str(cfg.get("iso_map_file", "config/iso_to_wiki.json"))
    iso_path = repo / iso_map_rel
    iso_map = _read_json(iso_path)
    if not isinstance(iso_map, dict):
        raise SystemExit(f"❌ Missing/invalid iso_to_wiki map: {iso_path}")

    out: Dict[str, Dict[str, str]] = {}
    for k, v in iso_map.items():
        if not (isinstance(k, str) and isinstance(v, dict)):
            continue
        wiki = v.get("wiki")
        name = v.get("name")
        if isinstance(wiki, str) and wiki.strip():
            out[k.strip().casefold()] = {
                "wiki": wiki.strip(),
                "name": name.strip() if isinstance(name, str) else "",
            }
    return out


def _invert_iso_map(iso_map: Mapping[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    Build a reverse index: wiki -> {"iso2": <best>, "iso3": <best>}
    Deterministic by sorted iso_map keys; iso2 preferred where available.
    """
    by_wiki: Dict[str, Dict[str, str]] = {}
    for k in sorted(iso_map.keys()):
        wiki = iso_map[k].get("wiki")
        if not isinstance(wiki, str) or not wiki.strip():
            continue
        if wiki not in by_wiki:
            by_wiki[wiki] = {}
        if len(k) == 2 and "iso2" not in by_wiki[wiki]:
            by_wiki[wiki]["iso2"] = k
        if len(k) == 3 and "iso3" not in by_wiki[wiki]:
            by_wiki[wiki]["iso3"] = k
    return by_wiki


def _resolve_profiles_path(cfg: Mapping[str, Any]) -> Optional[Path]:
    """
    Tries frontend profiles_path first; if missing or invalid, falls back to backend profiles.json.
    """
    repo = _project_root()
    fe_cfg = cfg.get("frontend") if isinstance(cfg.get("frontend"), dict) else {}
    fe_profiles_rel = str(
        (fe_cfg or {}).get(
            "profiles_path", "architect_frontend/src/config/language_profiles.json"
        )
    )
    backend_profiles_rel = str(
        cfg.get("backend_profiles_path", "app/core/config/profiles/profiles.json")
    )

    for p in (repo / fe_profiles_rel, repo / backend_profiles_rel):
        if p.is_file():
            return p
    return None


def _iter_profiles(obj: Any) -> Iterable[Mapping[str, Any]]:
    """
    Supports:
      - dict of profiles: { "eng": {...}, "fra": {...} }
      - list of profiles: [ {...}, {...} ]
    """
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, Mapping):
                yield v
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, Mapping):
                yield v


def _profile_iso_codes(profile: Mapping[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (iso3, iso2) if present.
    We prefer 3-letter keys used in backend profiles (eng/fra/etc).
    """
    iso3 = (
        profile.get("language_code")
        or profile.get("iso3")
        or profile.get("bcp47")
        or profile.get("lang3")
    )
    iso2 = profile.get("iso") or profile.get("iso2") or profile.get("lang")
    iso3_s = iso3.strip().casefold() if isinstance(iso3, str) else None
    iso2_s = iso2.strip().casefold() if isinstance(iso2, str) else None
    return iso3_s, iso2_s


def _wiki_code_from_profile(
    profile: Mapping[str, Any], iso_map: Mapping[str, Dict[str, str]]
) -> Optional[str]:
    """
    Determines the 3-letter Wiki code (e.g. Eng, Fre) for a profile.
    Accepts:
      - explicit wiki_code in profile
      - ISO codes resolved via iso_to_wiki.json
    """
    w = profile.get("wiki_code")
    if isinstance(w, str) and len(w.strip()) == 3:
        return w.strip()

    iso3, iso2 = _profile_iso_codes(profile)
    if iso3 and iso3 in iso_map:
        return iso_map[iso3]["wiki"]
    if iso2 and iso2 in iso_map:
        return iso_map[iso2]["wiki"]
    return None


def _clamp10(x: int) -> int:
    return 0 if x < 0 else 10 if x > 10 else x


def _score_profile(profile: Mapping[str, Any], resolved_wiki: Optional[str]) -> int:
    """
    Heuristic maturity scoring for a profile entry.
    """
    if not profile:
        return ABSENT

    iso3, iso2 = _profile_iso_codes(profile)
    signal_fields = 0
    if iso3:
        signal_fields += 1
    if iso2:
        signal_fields += 1
    if resolved_wiki:
        signal_fields += 1
    if isinstance(profile.get("name") or profile.get("display_name"), str):
        signal_fields += 1

    if signal_fields <= 2:
        return PLANNED

    score = SCAFFOLDED

    # Core identity fields
    if iso3:
        score += 1
    if iso2:
        score += 1
    if resolved_wiki:
        score += 1
    if isinstance(profile.get("name") or profile.get("display_name"), str):
        score += 1

    # Operational fields
    if isinstance(profile.get("enabled"), bool):
        score += 1
    if isinstance(profile.get("morphology_config_path"), str) and profile.get(
        "morphology_config_path"
    ).strip():
        score += 1

    # Extra quality signals
    if isinstance(profile.get("family"), str) and profile.get("family").strip():
        score += 1
    if isinstance(profile.get("script"), str) and profile.get("script").strip():
        score += 1
    feats = profile.get("features") or profile.get("capabilities")
    if isinstance(feats, dict) and len(feats) > 0:
        score += 1
    if isinstance(profile.get("notes") or profile.get("source"), str):
        score += 1

    score = _clamp10(score)
    if score <= 4:
        return SCAFFOLDED
    if score <= 6:
        return DRAFT
    if score <= 7:
        return BETA
    if score <= 9:
        return PRE_FINAL
    return FINAL


def _score_assets(has_profile: bool, has_flag: bool) -> int:
    if has_flag:
        return FINAL
    if has_profile:
        return PLANNED
    return ABSENT


def _score_routes(
    repo: Path,
    profile: Optional[Mapping[str, Any]],
    iso2_hint: Optional[str],
    iso3_hint: Optional[str],
) -> int:
    if not profile:
        return ABSENT

    mpath = profile.get("morphology_config_path")
    if not (isinstance(mpath, str) and mpath.strip()):
        return SCAFFOLDED

    p = repo / mpath
    if not p.is_file():
        return PLANNED

    obj = _read_json(p)
    if not isinstance(obj, dict):
        return DRAFT

    lang_container = None
    if isinstance(obj.get("languages"), dict):
        lang_container = obj["languages"]
    elif isinstance(obj.get("langs"), dict):
        lang_container = obj["langs"]

    if not isinstance(lang_container, dict):
        return BETA

    keys_to_try = [
        k for k in (iso2_hint, iso3_hint) if isinstance(k, str) and k.strip()
    ]
    found_key = next((k for k in keys_to_try if k in lang_container), None)
    if not found_key:
        return DRAFT

    entry = lang_container.get(found_key)
    if isinstance(entry, dict) and (entry.get("gold") is True or entry.get("validated") is True):
        return FINAL

    if entry in (None, {}, []):
        return BETA

    if isinstance(entry, dict):
        for k in ("structure", "articles", "topology", "morphology", "rules"):
            if k in entry and entry.get(k) not in (None, {}, [], ""):
                return PRE_FINAL
        return BETA

    return BETA


@dataclass(frozen=True)
class _DialogSpec:
    path: Path


def _score_assistant_dialog(
    repo: Path, iso2: Optional[str], iso3: Optional[str], cfg: Mapping[str, Any]
) -> int:
    """
    Assistant/dialog maturity from artifacts.
    Default lookup: data/lexicon/<iso>/dialog.json (iso2 preferred, fallback iso3).
    """
    lex_root_rel = str(cfg.get("lexicon_root", "data/lexicon"))
    lex_root = repo / lex_root_rel

    candidates: list[Path] = []
    for iso in (iso2, iso3):
        if isinstance(iso, str) and iso.strip():
            candidates.append(lex_root / iso / "dialog.json")
            candidates.append(lex_root / iso / "assistant.json")

    found: Optional[_DialogSpec] = None
    for p in candidates:
        if p.is_file():
            found = _DialogSpec(path=p)
            break

    if not found:
        return ABSENT

    obj = _read_json(found.path)
    if obj is None:
        return SCAFFOLDED

    unit_count = 0
    if isinstance(obj, list):
        unit_count = len(obj)
    elif isinstance(obj, dict):
        if isinstance(obj.get("intents"), list):
            unit_count = len(obj["intents"])
        elif isinstance(obj.get("dialogs"), list):
            unit_count = len(obj["dialogs"])
        elif isinstance(obj.get("items"), list):
            unit_count = len(obj["items"])
        else:
            unit_count = len(obj.keys())

        if obj.get("gold") is True or obj.get("validated") is True:
            return FINAL

    if unit_count <= 0:
        return SCAFFOLDED
    if unit_count <= 2:
        return DRAFT
    if unit_count <= 8:
        return BETA
    if unit_count <= 25:
        return PRE_FINAL
    return FINAL


def scan_application(*, key_mode: str = "iso2") -> Dict[str, Dict[str, int]]:
    """
    Scans the Application layer (Frontend & Backend Configs).

    Default output is keyed by ISO-639-1 (iso2, lowercase) to match everything_matrix.
    For backward compatibility, key_mode="wiki" returns the wiki-keyed map.

    Output blocks per language:
      - app_profile, app_assets, app_routes, app_asst (0..10)
      - PROF, ASST, ROUT (0..10) for Everything Matrix Zone C
    """
    key_mode = (key_mode or "iso2").strip().casefold()
    if key_mode not in {"iso2", "wiki"}:
        key_mode = "iso2"

    cfg = load_config()
    repo = _project_root()

    fe_cfg = cfg.get("frontend") if isinstance(cfg.get("frontend"), dict) else {}
    assets_rel = str((fe_cfg or {}).get("assets_path", "architect_frontend/public/flags"))
    assets_path = repo / assets_rel

    iso_map = _load_iso_to_wiki_map(cfg)
    inv = _invert_iso_map(iso_map)

    # Internal accumulator keyed by wiki for scanning, then normalized to iso2.
    by_wiki: Dict[str, Dict[str, int]] = {}

    # 1) PROFILES
    profiles_path = _resolve_profiles_path(cfg)
    profiles_obj = _read_json(profiles_path) if profiles_path else None

    profiles_by_wiki: Dict[str, Mapping[str, Any]] = {}
    if profiles_path and profiles_obj is not None:
        for prof in _iter_profiles(profiles_obj):
            wiki = _wiki_code_from_profile(prof, iso_map)
            if not wiki:
                continue
            if wiki not in profiles_by_wiki:
                profiles_by_wiki[wiki] = prof

            prof_score = _score_profile(prof, wiki)
            by_wiki.setdefault(wiki, {})["app_profile"] = prof_score
    else:
        logger.warning("No profiles file found (checked frontend + backend fallback).")

    # 2) UI ASSETS (FLAGS)
    flags_by_wiki: Dict[str, bool] = {}
    if assets_path.is_dir():
        for svg in sorted(assets_path.glob("*.svg")):
            stem = svg.stem.strip()
            if not stem:
                continue

            wiki: Optional[str] = None

            # Case A: Wiki code file name (Eng.svg)
            if len(stem) == 3 and stem[0].isupper():
                wiki = stem.strip()
            else:
                # Case B: ISO file name (fr.svg, fra.svg, eng.svg, etc.)
                key = stem.casefold()
                hit = iso_map.get(key)
                if hit:
                    wiki = hit.get("wiki")

            if wiki:
                flags_by_wiki[wiki] = True
                by_wiki.setdefault(wiki, {})["app_assets"] = FINAL
    else:
        logger.warning("Assets path not found: %s", assets_path)

    # Ensure deterministic planned/absent scoring for assets where profile exists
    for wiki in profiles_by_wiki.keys():
        has_profile = True
        has_flag = flags_by_wiki.get(wiki, False)
        by_wiki.setdefault(wiki, {})["app_assets"] = _score_assets(has_profile, has_flag)

    # 3) BACKEND ROUTES / WIRING (morphology config)
    for wiki, prof in profiles_by_wiki.items():
        iso2_hint = inv.get(wiki, {}).get("iso2")
        iso3_hint = inv.get(wiki, {}).get("iso3")
        route_score = _score_routes(repo=repo, profile=prof, iso2_hint=iso2_hint, iso3_hint=iso3_hint)
        by_wiki.setdefault(wiki, {})["app_routes"] = route_score

    # 4) ASSISTANT / DIALOG readiness (from lexicon artifacts)
    for wiki in list(by_wiki.keys()):
        iso2 = inv.get(wiki, {}).get("iso2")
        iso3 = inv.get(wiki, {}).get("iso3")
        asst_score = _score_assistant_dialog(repo=repo, iso2=iso2, iso3=iso3, cfg=cfg)
        by_wiki.setdefault(wiki, {})["app_asst"] = asst_score

    # 5) Aliases / synthesis
    for wiki, blk in by_wiki.items():
        app_profile = int(blk.get("app_profile", ABSENT))
        app_assets = int(blk.get("app_assets", ABSENT))
        app_routes = int(blk.get("app_routes", ABSENT))
        app_asst = int(blk.get("app_asst", ABSENT))

        prof = _clamp10(round(0.7 * app_profile + 0.3 * app_assets))
        blk["PROF"] = int(prof)
        blk["ASST"] = int(app_asst)
        blk["ROUT"] = int(app_routes)

    if key_mode == "wiki":
        return {k: by_wiki[k] for k in sorted(by_wiki.keys())}

    # Normalize to iso2 for Everything Matrix (deterministic: sorted wiki)
    by_iso2: Dict[str, Dict[str, int]] = {}
    for wiki in sorted(by_wiki.keys()):
        blk = by_wiki[wiki]
        iso2 = inv.get(wiki, {}).get("iso2")
        if not (isinstance(iso2, str) and len(iso2.strip()) == 2):
            continue
        k = iso2.strip().casefold()
        if k not in by_iso2:
            by_iso2[k] = {kk: int(vv) for kk, vv in blk.items()}

    return {k: by_iso2[k] for k in sorted(by_iso2.keys())}


# --- APIs expected by build_index.py (fast + iso2-keyed) ---


def scan_all_apps(repo_root: Optional[Path] = None) -> Dict[str, Dict[str, int]]:
    """
    Return app readiness keyed by iso2 (lowercase).
    `repo_root` is accepted for orchestrator compatibility; root is resolved internally.
    """
    _ = repo_root
    return scan_application(key_mode="iso2")


def scan_app_health(iso: str, repo_root: Optional[Path] = None) -> Dict[str, int]:
    """
    Return Zone C for a single language keyed by "PROF/ASST/ROUT".
    """
    _ = repo_root
    iso2 = (iso or "").strip().casefold()
    all_scores = scan_all_apps()
    row = all_scores.get(iso2)
    if isinstance(row, dict):
        return {
            "PROF": int(row.get("PROF", 0)),
            "ASST": int(row.get("ASST", 0)),
            "ROUT": int(row.get("ROUT", 0)),
        }
    return {"PROF": 0, "ASST": 0, "ROUT": 0}


if __name__ == "__main__":
    with tool_logging("app_scanner") as ctx:
        ctx.log_stage("Configuration")
        # Logic to resolve paths...
        repo = _project_root()
        
        ctx.log_stage("Scanning Profiles & Assets")
        results = scan_application(key_mode="iso2")
        
        # Prepare Metadata
        meta = {
            "scanner": SCANNER_VERSION,
            "generated_at": int(time.time()),
            "generated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "count": len(results),
            "root": str(repo),
            "key_mode": "iso2"
        }
        
        # Diagnostics
        diagnostics = []
        if len(results) == 0:
            diagnostics.append("Warning: No profiles found. Check language_profiles.json.")
        
        output = {
            "meta": meta,
            "languages": results,
            "diagnostics": diagnostics
        }
        
        # Print JSON to stdout (for GUI consumption)
        print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
        
        ctx.finish({"languages_scanned": len(results)})