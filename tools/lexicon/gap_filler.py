# tools/lexicon/gap_filler.py
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

# Add project root for utils import
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from utils.tool_run_logging import tool_logging  # noqa: E402

# Default lexicon location (current layout)
DEFAULT_DATA_DIR = root_dir / "data" / "lexicon"


# ---------------------------------------------------------------------------
# ISO normalization (reuse Everything Matrix normalizer when available)
# ---------------------------------------------------------------------------

def _discover_iso_map_path(repo_root: Path) -> Optional[Path]:
    candidates = [
        repo_root / "data" / "config" / "iso_to_wiki.json",
        repo_root / "config" / "iso_to_wiki.json",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _load_norm_helpers() -> Tuple[Optional[Any], Optional[Any], Optional[Any]]:
    """
    Try to import:
      - load_iso_to_wiki
      - build_wiki_to_iso2
      - norm_to_iso2
    from tools/everything_matrix/norm.py (single source of truth).
    """
    em_dir = root_dir / "tools" / "everything_matrix"
    if em_dir.is_dir() and str(em_dir) not in sys.path:
        sys.path.append(str(em_dir))
    try:
        from norm import load_iso_to_wiki, build_wiki_to_iso2, norm_to_iso2  # type: ignore
        return load_iso_to_wiki, build_wiki_to_iso2, norm_to_iso2
    except Exception:
        return None, None, None


def _build_wiki_to_iso2_fallback(iso_to_wiki: Mapping[str, Any]) -> Dict[str, str]:
    """
    Minimal fallback compatible with v1/v2 iso_to_wiki.json formats.
    Builds (iso2 key | iso3 key | wiki code | 'wiki'+wiki code) -> preferred iso2
    """
    preferred_by_wiki: Dict[str, str] = {}

    # v2 objects: prefer iso2 keys for each wiki code
    for k, v in iso_to_wiki.items():
        if not (isinstance(k, str) and isinstance(v, Mapping)):
            continue
        kk = k.strip().casefold()
        if len(kk) != 2:
            continue
        wiki = v.get("wiki")
        if isinstance(wiki, str) and wiki.strip():
            preferred_by_wiki[wiki.strip().casefold()] = kk

    wiki_to_iso2: Dict[str, str] = {}

    # v2 objects: map iso2/iso3 keys and wiki codes back to preferred iso2
    for k, v in iso_to_wiki.items():
        if not (isinstance(k, str) and isinstance(v, Mapping)):
            continue
        kk = k.strip().casefold()
        wiki = v.get("wiki")
        if not (isinstance(wiki, str) and wiki.strip()):
            continue
        wk = wiki.strip().casefold()
        iso2 = preferred_by_wiki.get(wk)
        if iso2 and len(iso2) == 2:
            wiki_to_iso2[kk] = iso2
            wiki_to_iso2[wk] = iso2
            wiki_to_iso2[f"wiki{wk}"] = iso2

    # v1: {"en":"Eng"} style
    for k, v in iso_to_wiki.items():
        if not isinstance(k, str):
            continue
        kk = k.strip().casefold()
        if len(kk) != 2 or not kk.isalpha():
            continue
        if isinstance(v, str) and v.strip():
            wk = v.strip().casefold()
            wiki_to_iso2[kk] = kk
            wiki_to_iso2[wk] = kk
            wiki_to_iso2[f"wiki{wk}"] = kk

    return wiki_to_iso2


def _load_wiki_to_iso2(repo_root: Path) -> Dict[str, str]:
    iso_map_path = _discover_iso_map_path(repo_root)
    if not iso_map_path:
        return {}

    try:
        raw = json.loads(iso_map_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    load_iso_to_wiki, build_wiki_to_iso2, _ = _load_norm_helpers()
    if load_iso_to_wiki and build_wiki_to_iso2:
        try:
            iso_to_wiki = load_iso_to_wiki(iso_map_path)  # type: ignore[misc]
            return build_wiki_to_iso2(iso_to_wiki)  # type: ignore[misc]
        except Exception:
            pass

    if isinstance(raw, dict):
        return _build_wiki_to_iso2_fallback(raw)
    return {}


def _norm_to_iso2(code: str, wiki_to_iso2: Mapping[str, str]) -> Optional[str]:
    _, _, norm_to_iso2 = _load_norm_helpers()
    if norm_to_iso2:
        try:
            return norm_to_iso2(code, wiki_to_iso2=wiki_to_iso2)  # type: ignore[misc]
        except Exception:
            pass

    if not isinstance(code, str):
        return None
    k = code.strip().casefold()
    if not k:
        return None
    hit = wiki_to_iso2.get(k)
    if isinstance(hit, str) and len(hit) == 2:
        return hit
    if len(k) == 2 and k.isalpha():
        return k
    return None


# ---------------------------------------------------------------------------
# Lexicon loading (supports new shard layout + legacy flat files)
# ---------------------------------------------------------------------------

def _unwrap_lexicon_obj(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        return {}
    if isinstance(obj.get("lexicon"), dict):
        return obj["lexicon"]  # type: ignore[return-value]
    if isinstance(obj.get("entries"), dict):
        return obj["entries"]  # type: ignore[return-value]
    return obj


def _resolve_lexicon_root(data_dir: Path) -> Path:
    """
    Accepts:
      - data/lexicon                (preferred)
      - data                         (will use data/lexicon if present)
      - any directory that directly contains language folders
    """
    if (data_dir / "lexicon").is_dir():
        return data_dir / "lexicon"
    return data_dir


def _resolve_language_dir(lex_root: Path, iso2: Optional[str], raw_code: str) -> Optional[Path]:
    """
    New layout: data/lexicon/{iso2}/(wide.json, core.json, ...)
    Fallback: try raw code as folder name.
    """
    if iso2:
        d = lex_root / iso2
        if d.is_dir():
            return d

    raw = raw_code.strip().casefold()
    if raw:
        d = lex_root / raw
        if d.is_dir():
            return d

    return None


def _find_legacy_language_file(base_dir: Path, lang_code: str) -> Optional[Path]:
    """
    Legacy layout: recursively searches for {lang_code}.json under base_dir.
    """
    if not base_dir.exists():
        return None

    direct = base_dir / f"{lang_code}.json"
    if direct.exists():
        return direct

    matches = list(base_dir.rglob(f"{lang_code}.json"))
    if matches:
        return matches[0]
    return None


def _load_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_lexicon_from_language_dir(lang_dir: Path) -> Dict[str, Any]:
    """
    Merge all JSON shard files in a language directory (new layout).
    """
    merged: Dict[str, Any] = {}
    if not lang_dir.is_dir():
        return merged

    # Prefer known shards first (stable ordering), then any other json files.
    preferred = ["wide.json", "core.json", "people.json", "science.json", "geography.json"]
    seen: set[Path] = set()

    for name in preferred:
        p = lang_dir / name
        if p.is_file():
            seen.add(p)
            obj = _load_json(p)
            part = _unwrap_lexicon_obj(obj)
            for k, v in part.items():
                if isinstance(k, str):
                    merged.setdefault(k, v)

    for p in sorted(lang_dir.glob("*.json"), key=lambda x: x.name):
        if p in seen:
            continue
        obj = _load_json(p)
        part = _unwrap_lexicon_obj(obj)
        # Skip obvious non-lexicon JSON blobs
        if not part:
            continue
        for k, v in part.items():
            if isinstance(k, str):
                merged.setdefault(k, v)

    return merged


def load_lexicon(path: Path) -> Dict[str, Any]:
    obj = _load_json(path)
    return _unwrap_lexicon_obj(obj)


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------

def analyze_gaps(pivot_data: Dict[str, Any], target_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns a list of items present in Pivot but missing in Target.
    """
    gaps: List[Dict[str, Any]] = []
    pivot_keys = {k for k in pivot_data.keys() if isinstance(k, str) and not k.startswith("_")}

    for key in sorted(pivot_keys):
        if key not in target_data:
            parts = key.split("_")
            category = parts[-1] if len(parts) > 1 else "Unknown"
            gaps.append(
                {
                    "key": key,
                    "category": category,
                    "pivot_gloss": pivot_data.get(key),
                }
            )
    return gaps


def main() -> None:
    parser = argparse.ArgumentParser(description="Find missing lexicon entries.")
    parser.add_argument("--target", required=True, help="Target language code (iso2/iso3/wiki).")
    parser.add_argument("--pivot", default="en", help="Pivot language code (iso2/iso3/wiki).")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Path to lexicon root or data directory.")
    parser.add_argument("--json-out", help="Path to save the gap report as JSON.")
    parser.add_argument("--verbose", action="store_true", help="Print missing summary to console.")

    args = parser.parse_args()

    with tool_logging("gap_filler") as ctx:
        ctx.log_stage("Initialization")

        base_path = Path(args.data_dir).resolve()
        lex_root = _resolve_lexicon_root(base_path)

        wiki_to_iso2 = _load_wiki_to_iso2(root_dir)
        pivot_iso2 = _norm_to_iso2(args.pivot, wiki_to_iso2)
        target_iso2 = _norm_to_iso2(args.target, wiki_to_iso2)

        ctx.logger.info(f"Pivot (raw):  {args.pivot}  -> iso2={pivot_iso2 or 'N/A'}")
        ctx.logger.info(f"Target (raw): {args.target} -> iso2={target_iso2 or 'N/A'}")
        ctx.logger.info(f"Data Dir: {base_path}")
        ctx.logger.info(f"Lexicon Root: {lex_root}")

        # 1) Resolve new-layout directories
        pivot_dir = _resolve_language_dir(lex_root, pivot_iso2, args.pivot)
        target_dir = _resolve_language_dir(lex_root, target_iso2, args.target)

        pivot_lex: Dict[str, Any] = {}
        target_lex: Dict[str, Any] = {}

        if pivot_dir and target_dir:
            ctx.logger.info(f"Found Pivot Dir:  {pivot_dir.relative_to(root_dir) if pivot_dir.is_relative_to(root_dir) else pivot_dir}")
            ctx.logger.info(f"Found Target Dir: {target_dir.relative_to(root_dir) if target_dir.is_relative_to(root_dir) else target_dir}")
            pivot_lex = load_lexicon_from_language_dir(pivot_dir)
            target_lex = load_lexicon_from_language_dir(target_dir)
        else:
            # 2) Legacy fallback: {code}.json anywhere under base_path
            ctx.logger.info("New-layout language folder not found for one/both languages; trying legacy file layout...")
            pivot_candidates = [pivot_iso2, args.pivot]
            target_candidates = [target_iso2, args.target]

            pivot_path = None
            for c in pivot_candidates:
                if c:
                    pivot_path = _find_legacy_language_file(base_path, str(c).casefold())
                    if pivot_path:
                        break

            target_path = None
            for c in target_candidates:
                if c:
                    target_path = _find_legacy_language_file(base_path, str(c).casefold())
                    if target_path:
                        break

            if not pivot_path:
                ctx.logger.error(f"Pivot lexicon not found for '{args.pivot}' under {base_path}")
                sys.exit(1)

            if not target_path:
                ctx.logger.error(f"Target lexicon not found for '{args.target}' under {base_path}")
                sys.exit(1)

            ctx.logger.info(f"Found Pivot File:  {pivot_path.relative_to(root_dir) if pivot_path.is_relative_to(root_dir) else pivot_path}")
            ctx.logger.info(f"Found Target File: {target_path.relative_to(root_dir) if target_path.is_relative_to(root_dir) else target_path}")

            pivot_lex = load_lexicon(pivot_path)
            target_lex = load_lexicon(target_path)

        if not pivot_lex:
            ctx.logger.error("Pivot lexicon is empty or invalid.")
            sys.exit(1)

        # 3) Analyze
        ctx.log_stage("Analyzing Gaps")
        gaps = analyze_gaps(pivot_lex, target_lex)

        total_pivot = len([k for k in pivot_lex.keys() if isinstance(k, str) and not k.startswith("_")])
        total_target = len([k for k in target_lex.keys() if isinstance(k, str) and not k.startswith("_")])
        missing_count = len(gaps)
        coverage = ((total_pivot - missing_count) / total_pivot) * 100 if total_pivot > 0 else 0.0

        # 4) Summary
        ctx.logger.info(f"Total Concepts (Pivot): {total_pivot}")
        ctx.logger.info(f"Total Concepts (Target): {total_target}")
        ctx.logger.info(f"Missing Entries: {missing_count}")
        ctx.logger.info(f"Coverage: {coverage:.1f}%")

        if args.verbose and gaps:
            ctx.log_stage("Detailed Gaps (sample)")
            by_cat: Dict[str, List[Dict[str, Any]]] = {}
            for g in gaps:
                by_cat.setdefault(g["category"], []).append(g)

            for cat, items in sorted(by_cat.items(), key=lambda kv: kv[0]):
                ctx.logger.info(f"[{cat}] ({len(items)})")
                for item in items[:10]:
                    ctx.logger.info(f"  - {item['key']}: {item.get('pivot_gloss')}")
                if len(items) > 10:
                    ctx.logger.info(f"    ... and {len(items) - 10} more.")

        # 5) Export
        report_file = "N/A"
        if args.json_out:
            out_path = Path(args.json_out).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)

            report = {
                "target_raw": args.target,
                "pivot_raw": args.pivot,
                "target_iso2": target_iso2,
                "pivot_iso2": pivot_iso2,
                "stats": {
                    "total_pivot": total_pivot,
                    "total_target": total_target,
                    "coverage_percent": round(coverage, 3),
                    "missing_count": missing_count,
                },
                "missing": gaps,
            }
            try:
                out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
                report_file = str(out_path)
                ctx.logger.info(f"✅ Report saved to: {out_path}")
            except Exception as e:
                ctx.logger.error(f"Failed to save report: {e}")

        ctx.finish(
            {
                "target": args.target,
                "pivot": args.pivot,
                "missing": missing_count,
                "coverage": round(coverage, 1),
                "report_file": report_file,
            }
        )


if __name__ == "__main__":
    main()