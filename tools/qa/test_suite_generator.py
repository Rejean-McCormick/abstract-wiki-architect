# tools/qa/test_suite_generator.py
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

# --- Configuration ---
# Define paths relative to this script
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
# Default matrix file location
DEFAULT_MATRIX_FILE = DATA_DIR / "indices" / "everything_matrix.json"
# Default output location
DEFAULT_OUTPUT_DIR = DATA_DIR / "tests" / "templates"

# Standard Test Cases (The "BioFrame" Smoke Test)
BASE_TEST_CASES = [
    # (ID Suffix, Name, Gender, Profession, Nationality)
    ("001", "Roberto", "m", "Actor", "Italian"),
    ("002", "Maria", "f", "Actor", "Italian"),
    ("003", "Enrico", "m", "Scientist", "Italian"),  # Test: S+Consonant checks
    ("004", "Sofia", "f", "Scientist", "Italian"),
    ("005", "Pablo", "m", "Painter", "Spanish"),
    ("006", "Frida", "f", "Painter", "Spanish"),
    ("007", "Jean", "m", "Writer", "French"),
    ("008", "Simone", "f", "Writer", "French"),
    ("009", "Dante", "m", "Poet", "Italian"),        # Test: Irregular forms
    ("010", "Marie", "f", "Physicist", "Polish"),
    ("011", "Albert", "m", "Physicist", "German"),
    ("012", "Ada", "f", "Programmer", "British"),
]

def print_header(matrix_file: Path, output_dir: Path):
    print("========================================")
    print("   TEST SUITE GENERATOR (TEMPLATE)")
    print("========================================")
    print(f"Time:       {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Root:       {PROJECT_ROOT}")
    print(f"Matrix:     {matrix_file}")
    print(f"Output Dir: {output_dir}")
    print("----------------------------------------")
    sys.stdout.flush()

def load_everything_matrix(matrix_file: Path) -> Dict[str, Any]:
    """Loads the central language registry."""
    if not matrix_file.exists():
        print(f"❌ Error: Matrix file not found at {matrix_file}")
        print("   Hint: Run 'python tools/everything_matrix/build_index.py' first.")
        sys.exit(1)
    
    try:
        with open(matrix_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Matrix file is invalid JSON: {e}")
        sys.exit(1)

def generate_csv_templates(
    langs_filter: Optional[List[str]],
    output_dir: Path,
    matrix_file: Path,
    verbose: bool
) -> None:
    """
    Generates CSV testing templates for languages defined in the Everything Matrix.
    """
    start_time = time.time()
    
    matrix = load_everything_matrix(matrix_file)
    languages = matrix.get("languages", {})

    if not languages:
        print("⚠️  No languages found in the Matrix.")
        return

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_count = 0
    skipped_count = 0
    total_bytes = 0
    
    # Normalize filter
    target_set: Optional[Set[str]] = None
    if langs_filter:
        target_set = {l.lower().strip() for l in langs_filter if l.strip()}
        if verbose:
            print(f"🔍 Filtering for languages: {sorted(target_set)}")

    # Iterate over matrix
    # Matrix keys are typically ISO-2 (lowercase)
    sorted_keys = sorted(languages.keys())
    
    for iso_code in sorted_keys:
        lang_data = languages[iso_code]
        
        # 1. Check Filter
        if target_set and iso_code.lower() not in target_set:
            continue

        meta = lang_data.get("meta", {})
        verdict = lang_data.get("verdict", {})
        
        lang_name = meta.get("name", iso_code)
        strategy = verdict.get("build_strategy", "UNKNOWN")

        # 2. Skip non-runnable if we want to be strict, 
        # but usually we want templates even for partial langs.
        # Let's just skip explicit 'SKIP' strategies unless forced?
        # For now, we generate for anything in the matrix to encourage development.
        if strategy == "SKIP":
            if verbose:
                print(f"   [SKIP] {iso_code} (Strategy: SKIP)")
            skipped_count += 1
            continue

        # 3. Generate File
        filename = output_dir / f"test_suite_{iso_code}.csv"
        
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                # Header Columns — Aligned with QA Runner expectations
                writer.writerow([
                    "Test_ID",
                    "Frame_Type",
                    "Name",
                    "Gender",
                    "Profession_ID",
                    "Nationality_ID",
                    "EXPECTED_TEXT" 
                ])

                # Write rows
                for suffix, name, gender, prof, nat in BASE_TEST_CASES:
                    test_id = f"{iso_code.upper()}_BIO_{suffix}"
                    
                    # We use placeholder QIDs or English concepts as hints
                    writer.writerow([
                        test_id,
                        "bio",
                        name,
                        gender,
                        f"Q_{prof.upper()}", # Placeholder for QID/Concept
                        f"Q_{nat.upper()}",  # Placeholder for QID/Concept
                        "" # Empty column for the Human/Judge to fill
                    ])
            
            f_size = filename.stat().st_size
            total_bytes += f_size
            generated_count += 1
            
            if verbose:
                print(f"   [OK]   {iso_code:<5} -> {filename.name} ({f_size} bytes)")
            else:
                # Minimal progress indicator
                print(f"   ✅ Generated: {filename.name} ({lang_name})")
                
        except Exception as e:
            print(f"❌ Failed to generate {iso_code}: {e}")

    duration = time.time() - start_time
    
    print("----------------------------------------")
    print("   SUMMARY")
    print("----------------------------------------")
    print(f"Generated:   {generated_count} templates")
    print(f"Skipped:     {skipped_count}")
    print(f"Total Bytes: {total_bytes}")
    print(f"Duration:    {duration:.2f}s")
    print("========================================")

def main():
    parser = argparse.ArgumentParser(description="Generate CSV test templates for QA.")
    
    parser.add_argument(
        "--langs", 
        help="Comma-separated list of ISO codes to generate (e.g. 'en,fr,de'). Default: all."
    )
    parser.add_argument(
        "--out", 
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})."
    )
    parser.add_argument(
        "--matrix",
        help=f"Path to everything_matrix.json (default: {DEFAULT_MATRIX_FILE})."
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable detailed logging."
    )

    args = parser.parse_args()

    # Resolve paths
    matrix_path = Path(args.matrix) if args.matrix else DEFAULT_MATRIX_FILE
    out_path = Path(args.out) if args.out else DEFAULT_OUTPUT_DIR
    
    # Parse langs
    lang_list = None
    if args.langs:
        lang_list = [l.strip() for l in args.langs.split(",") if l.strip()]

    print_header(matrix_path, out_path)
    
    generate_csv_templates(
        langs_filter=lang_list, 
        output_dir=out_path, 
        matrix_file=matrix_path, 
        verbose=args.verbose
    )

if __name__ == "__main__":
    main()