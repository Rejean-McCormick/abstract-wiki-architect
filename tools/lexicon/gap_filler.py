# tools/lexicon/gap_filler.py
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root for utils import
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from utils.tool_run_logging import tool_logging

# Default data location relative to this script
DEFAULT_DATA_DIR = root_dir / "data"


def find_language_file(base_dir: Path, lang_code: str) -> Optional[Path]:
    """
    recursively searches for {lang_code}.json in the data directory.
    Useful because languages are grouped by family (e.g. data/romance/fra.json).
    """
    if not base_dir.exists():
        return None
    
    # Check direct path first
    direct = base_dir / f"{lang_code}.json"
    if direct.exists():
        return direct

    # Recursive search
    matches = list(base_dir.rglob(f"{lang_code}.json"))
    if matches:
        return matches[0] # Return the first match
    
    return None


def load_lexicon(path: Path) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Support different schemas:
            # 1. Direct dict: {"cat_N": "chat", ...}
            # 2. Wrapped: {"lexicon": {"cat_N": ...}}
            if "lexicon" in data and isinstance(data["lexicon"], dict):
                return data["lexicon"]
            return data
    except Exception as e:
        # We rely on caller to log this, but return empty
        return {}


def analyze_gaps(pivot_data: Dict[str, Any], target_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns a list of items present in Pivot but missing in Target.
    """
    gaps = []
    
    # Filter for actual lexicon keys (ignoring metadata like "_meta" or "version")
    pivot_keys = {k for k in pivot_data.keys() if not k.startswith("_")}
    
    for key in pivot_keys:
        if key not in target_data:
            # Determine category from key suffix (standard GF convention: word_Cat)
            # e.g. "eat_V2" -> "V2", "apple_N" -> "N"
            parts = key.split('_')
            category = parts[-1] if len(parts) > 1 else "Unknown"
            
            gaps.append({
                "key": key,
                "category": category,
                "pivot_gloss": pivot_data[key]
            })
            
    return gaps


def main():
    parser = argparse.ArgumentParser(description="Find missing lexicon entries.")
    parser.add_argument("--target", required=True, help="Target language code (e.g. 'fra', 'zul').")
    parser.add_argument("--pivot", default="eng", help="Pivot language code (default: 'eng').")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Path to data directory.")
    parser.add_argument("--json-out", help="Path to save the gap report as JSON.")
    parser.add_argument("--verbose", action="store_true", help="Print all missing words to console.")
    
    args = parser.parse_args()
    
    with tool_logging("gap_filler") as ctx:
        base_path = Path(args.data_dir)
        ctx.log_stage("Initialization")
        ctx.logger.info(f"Target: {args.target}")
        ctx.logger.info(f"Pivot: {args.pivot}")
        ctx.logger.info(f"Data Dir: {base_path}")

        # 1. Locate Files
        pivot_path = find_language_file(base_path, args.pivot)
        target_path = find_language_file(base_path, args.target)

        if not pivot_path:
            ctx.logger.error(f"Pivot file for '{args.pivot}' not found in {base_path}")
            sys.exit(1)
            
        if not target_path:
            ctx.logger.error(f"Target file for '{args.target}' not found. Create it first.")
            sys.exit(1)

        ctx.logger.info(f"Found Pivot: {pivot_path.relative_to(root_dir)}")
        ctx.logger.info(f"Found Target: {target_path.relative_to(root_dir)}")

        # 2. Load Data
        pivot_lex = load_lexicon(pivot_path)
        target_lex = load_lexicon(target_path)
        
        if not pivot_lex:
            ctx.logger.error("Pivot lexicon is empty or invalid.")
            sys.exit(1)

        # 3. Analyze
        ctx.log_stage("Analyzing Gaps")
        gaps = analyze_gaps(pivot_lex, target_lex)
        total_pivot = len([k for k in pivot_lex.keys() if not k.startswith("_")])
        total_target = len([k for k in target_lex.keys() if not k.startswith("_")])
        missing_count = len(gaps)
        coverage = 0.0
        if total_pivot > 0:
            coverage = ((total_pivot - missing_count) / total_pivot) * 100

        # 4. Report Summary
        ctx.logger.info(f"Total Concepts (Pivot): {total_pivot}")
        ctx.logger.info(f"Total Concepts (Target): {total_target}")
        ctx.logger.info(f"Missing Entries: {missing_count}")
        ctx.logger.info(f"Coverage: {coverage:.1f}%")

        if args.verbose and gaps:
            ctx.log_stage("Detailed Gaps")
            # Group by category for nicer output
            by_cat = {}
            for g in gaps:
                by_cat.setdefault(g['category'], []).append(g)
            
            for cat, items in sorted(by_cat.items()):
                ctx.logger.info(f"[{cat}] ({len(items)})")
                for item in items[:10]: # Limit to 10 per category in console to avoid spam
                    ctx.logger.info(f"  - {item['key']}: {item['pivot_gloss']}")
                if len(items) > 10:
                    ctx.logger.info(f"    ... and {len(items) - 10} more.")

        # 5. Export
        if args.json_out:
            report = {
                "target": args.target,
                "pivot": args.pivot,
                "stats": {
                    "total_pivot": total_pivot,
                    "coverage_percent": coverage,
                    "missing_count": missing_count
                },
                "missing": gaps
            }
            try:
                with open(args.json_out, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                ctx.logger.info(f"✅ Report saved to: {args.json_out}")
            except Exception as e:
                ctx.logger.error(f"Failed to save report: {e}")

        # Final context summary
        ctx.finish({
            "target": args.target,
            "missing": missing_count,
            "coverage": round(coverage, 1),
            "report_file": args.json_out if args.json_out else "N/A"
        })

if __name__ == "__main__":
    main()