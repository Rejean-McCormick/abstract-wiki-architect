# tools/bootstrap_tier1.py
from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root for utils import
root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from utils.tool_run_logging import tool_logging

# The "Proper" Source of Truth
MATRIX_PATH = Path("data/indices/everything_matrix.json")
RGL_SRC_PATH = Path("gf-rgl/src")
APP_GF_PATH = Path("gf")

logger = logging.getLogger(__name__)


def detect_rgl_suffix(folder_path: Path) -> Optional[str]:
    """
    Scans a folder like 'gf-rgl/src/german' to find 'GrammarGer.gf'.
    Returns the suffix 'Ger'.
    """
    if not folder_path.exists():
        return None
    
    # Look for Grammar*.gf to identify the 3-letter RGL code
    pattern = str(folder_path / "Grammar*.gf")
    files = glob.glob(pattern)
    
    for f in files:
        filename = os.path.basename(f)
        if filename.startswith("Grammar") and filename.endswith(".gf"):
            suffix = filename[7:-3] # Strip 'Grammar' and '.gf'
            return suffix
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap Tier 1 Languages.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--langs", help="Comma-separated list of ISO codes to process (optional)")
    args = parser.parse_args()

    with tool_logging("bootstrap_tier1") as ctx:
        ctx.log_stage("Initialization")
        
        if not MATRIX_PATH.exists():
            ctx.logger.error(f"Matrix not found at {MATRIX_PATH}. Run 'build_index' first.")
            sys.exit(1)

        with open(MATRIX_PATH, "r", encoding="utf-8") as f:
            matrix = json.load(f)

        languages = matrix.get("languages", {})
        ctx.logger.info(f"Loaded {len(languages)} languages from matrix.")

        target_langs = set()
        if args.langs:
            target_langs = {l.strip().lower() for l in args.langs.split(",") if l.strip()}
            ctx.logger.info(f"Filtering for: {target_langs}")

        ctx.log_stage("Bootstrapping")
        
        count = 0
        skipped = 0
        updated = 0
        
        for iso_code, data in languages.items():
            if target_langs and iso_code not in target_langs:
                continue

            # 1. Filter: We only bootstrap Tier 1 (RGL) languages
            meta = data.get("meta", {})
            if meta.get("tier") != 1:
                if target_langs:
                    ctx.logger.warning(f"Skipping {iso_code}: Not Tier 1 (Tier={meta.get('tier')})")
                continue

            folder_name = meta.get("folder")
            if not folder_name:
                ctx.logger.warning(f"Skipping {iso_code}: No folder defined in matrix.")
                skipped += 1
                continue

            # 2. Resolution: Map ISO (deu) -> Folder (german) -> Suffix (Ger)
            rgl_folder_path = RGL_SRC_PATH / folder_name
            suffix = detect_rgl_suffix(rgl_folder_path)

            if not suffix:
                ctx.logger.warning(f"Skipping {iso_code}: Could not detect RGL suffix in {rgl_folder_path}")
                skipped += 1
                continue

            # 3. Action: Create the Bridge (SyntaxGer.gf)
            bridge_file = rgl_folder_path / f"Syntax{suffix}.gf"
            if not bridge_file.exists() or args.force:
                if not args.dry_run:
                    try:
                        with open(bridge_file, "w", encoding="utf-8") as f:
                            f.write(f"instance Syntax{suffix} of Syntax = Grammar{suffix} ** {{ flags coding=utf8 ; }};\n")
                        ctx.logger.info(f"Created/Updated Bridge: {bridge_file}")
                        updated += 1
                    except Exception as e:
                        ctx.logger.error(f"Failed to write bridge {bridge_file}: {e}")
                else:
                    ctx.logger.info(f"[DRY RUN] Would create bridge: {bridge_file}")
            
            # 4. Action: Create the Application Grammar (WikiDeu.gf)
            # Note: We capitalize the ISO code for the filename (WikiDeu) but link to RGL suffix (Ger)
            app_file = APP_GF_PATH / f"Wiki{iso_code.capitalize()}.gf"
            
            content = (
                f"concrete Wiki{iso_code.capitalize()} of AbstractWiki = WikiI with (Syntax = Syntax{suffix}) ** "
                f"open Syntax{suffix}, Paradigms{suffix} in {{ flags coding = utf8 ; }};\n"
            )
            
            if not app_file.exists() or args.force:
                if not args.dry_run:
                    try:
                        with open(app_file, "w", encoding="utf-8") as f:
                            f.write(content)
                        ctx.logger.info(f"Created/Updated App Grammar: {app_file}")
                        updated += 1
                    except Exception as e:
                        ctx.logger.error(f"Failed to write app grammar {app_file}: {e}")
                else:
                    ctx.logger.info(f"[DRY RUN] Would create app grammar: {app_file}")
            
            count += 1

        ctx.finish({
            "processed": count,
            "updated_files": updated,
            "skipped_errors": skipped,
            "mode": "DRY RUN" if args.dry_run else "LIVE"
        })


if __name__ == "__main__":
    main()