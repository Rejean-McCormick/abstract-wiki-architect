# builder/orchestrator.py
import os
import subprocess
import sys
import json
import logging
import concurrent.futures
import time
from pathlib import Path

# --- Setup Paths ---
# Calculate ROOT_DIR relative to: builder/orchestrator.py -> builder/ -> ROOT
ROOT_DIR = Path(__file__).parent.parent

# Add ROOT to sys.path to allow imports from 'utils' and 'app'
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# --- Imports ---
try:
    from utils.grammar_factory import generate_safe_mode_grammar
except ImportError:
    generate_safe_mode_grammar = None

# --- Configuration ---
# GUI Compatibility: Force logging to stdout
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout, force=True)
logger = logging.getLogger("Orchestrator")

GF_DIR = ROOT_DIR / "gf"
RGL_SRC = ROOT_DIR / "gf-rgl" / "src"
RGL_API = RGL_SRC / "api"
GENERATED_SRC = ROOT_DIR / "generated" / "src"
LOG_DIR = GF_DIR / "build_logs"
MATRIX_FILE = ROOT_DIR / "data" / "indices" / "everything_matrix.json"
ISO_MAP_FILE = ROOT_DIR / "data" / "config" / "iso_to_wiki.json"

# Ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_SRC.mkdir(parents=True, exist_ok=True)

def load_iso_map():
    """Loads the authoritative ISO -> GF Name mapping."""
    if not ISO_MAP_FILE.exists():
        logger.warning("⚠️ ISO Map not found. Falling back to TitleCase.")
        return {}
    try:
        with open(ISO_MAP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Failed to load ISO Map: {e}")
        return {}

# Load the map once at module level
ISO_MAP = load_iso_map()

def get_gf_name(code):
    """
    Standardizes naming using the Chart.
    Input:  'en' (ISO-2) OR 'eng' (Legacy ISO-3)
    Output: 'WikiEng.gf' (RGL Standard)
    """
    # 1. Lookup the value in the chart (e.g. 'en' -> 'WikiEng')
    raw_val = ISO_MAP.get(code, ISO_MAP.get(code.lower()))
    
    suffix = None
    if raw_val:
        # Handle Rich Objects (v2.0) or Strings (v1.0)
        if isinstance(raw_val, dict):
            val_str = raw_val.get("wiki", "")
        else:
            val_str = raw_val

        # Strip "Wiki" prefix to prevent "WikiWikiEng.gf"
        suffix = val_str.replace("Wiki", "")
    
    # 2. Fallback: Title Case
    if not suffix:
        suffix = code.title()
        
    return f"Wiki{suffix}.gf"

def load_matrix():
    if not MATRIX_FILE.exists():
        logger.warning("⚠️  Everything Matrix not found. Defaulting to empty.")
        return {}
    try:
        with open(MATRIX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error("❌ Corrupt Everything Matrix. Cannot proceed.")
        return {}

def ensure_source_exists(lang_code, strategy):
    """
    Ensures the .gf source file exists before compilation.
    If strategy is SAFE_MODE, it triggers the Factory/Architect Agent.
    """
    if strategy == "HIGH_ROAD":
        return True
    
    # SAFE_MODE (Tier 3) requires generation
    target_file = GENERATED_SRC / get_gf_name(lang_code)
    
    if not target_file.exists():
        logger.info(f"🔨 Generating grammar for {lang_code} -> {target_file.name} (Factory)...")
        if generate_safe_mode_grammar:
            try:
                code = generate_safe_mode_grammar(lang_code)
                with open(target_file, "w", encoding='utf-8') as f:
                    f.write(code)
                return True
            except Exception as e:
                logger.error(f"💥 Generation failed for {lang_code}: {e}")
                return False
        else:
            logger.error(f"❌ Grammar Factory not imported. Cannot generate {lang_code}.")
            return False
            
    return True

def compile_gf(lang_code, strategy):
    """
    Compiles a single language to a .gfo object file (Phase 1).
    """
    gf_filename = get_gf_name(lang_code)
    
    # Determine Source Path based on Strategy
    if strategy == "SAFE_MODE":
        file_path = GENERATED_SRC / gf_filename
    else:
        file_path = GF_DIR / gf_filename

    # CRITICAL: Path includes RGL, API, and Generated sources
    path_args = f"{RGL_SRC}:{RGL_API}:{GENERATED_SRC}:."
    
    cmd = ["gf", "-batch", "-path", path_args, "-c", str(file_path)]
    
    # Execute Compiler
    proc = subprocess.run(cmd, cwd=str(GF_DIR), capture_output=True, text=True)
    
    if proc.returncode != 0:
        # Log to file
        log_path = LOG_DIR / f"{gf_filename}.log"
        with open(log_path, "w", encoding='utf-8') as f:
            f.write(proc.stderr + "\n" + proc.stdout)
        
        # Log tail to stdout for GUI visibility
        logger.error(f"   [STDERR {lang_code}] {proc.stderr.strip()[-500:]}")
        logger.error(f"   [LOG] See {log_path}")
            
    return proc

def phase_1_verify(lang_code, strategy):
    """
    Phase 1: Verify compilation of individual languages.
    """
    if not ensure_source_exists(lang_code, strategy):
        return (lang_code, False, "Source Missing")

    proc = compile_gf(lang_code, strategy)
    
    if proc.returncode == 0:
        return (lang_code, True, "OK")
    
    error_msg = proc.stderr.strip() or proc.stdout.strip() or f"Unknown Error (Exit Code {proc.returncode})"
    return (lang_code, False, error_msg)

def phase_2_link(valid_langs_map):
    """
    Phase 2: Link all valid .gfo files into a single AbstractWiki.pgf binary.
    """
    start_time = time.time()
    logger.info("\n=== PHASE 2: LINKING PGF ===")
    
    if not valid_langs_map:
        logger.error("❌ No valid languages to link! Build aborted.")
        sys.exit(1)

    targets = []
    for code, strategy in valid_langs_map.items():
        lang_name = get_gf_name(code)
        if strategy == "SAFE_MODE":
            targets.append(str(GENERATED_SRC / lang_name))
        else:
            targets.append(lang_name)

    path_args = f"{RGL_SRC}:{RGL_API}:{GENERATED_SRC}:."
    
    cmd = ["gf", "-make", "-path", path_args, "-name", "AbstractWiki", "AbstractWiki.gf"] + targets

    logger.info(f"🔗 Linking {len(targets)} languages...")
    logger.info(f"   [CMD] {' '.join(cmd[:5])} ... ({len(targets)} files)")

    proc = subprocess.run(cmd, cwd=str(GF_DIR), capture_output=True, text=True)

    duration = time.time() - start_time
    
    if proc.returncode == 0:
        logger.info(f"✅ BUILD SUCCESS: AbstractWiki.pgf created in {duration:.2f}s")
        # Print binary size
        pgf_path = GF_DIR / "AbstractWiki.pgf"
        if pgf_path.exists():
            size_mb = pgf_path.stat().st_size / (1024 * 1024)
            logger.info(f"   [ARTIFACT] {pgf_path} ({size_mb:.2f} MB)")
    else:
        logger.error(f"❌ LINK FAILED in {duration:.2f}s")
        logger.error(f"   [STDERR]\n{proc.stderr.strip()}")

def main():
    start_global = time.time()
    
    matrix = load_matrix()
    tasks = []
    
    if matrix:
        for code, data in matrix.get("languages", {}).items():
            verdict = data.get("verdict", {})
            strategy = verdict.get("build_strategy", "SKIP")
            
            if strategy in ["HIGH_ROAD", "SAFE_MODE"]:
                tasks.append((code, strategy))
    else:
        logger.info("⚠️  Matrix empty. Using bootstrap defaults.")
        tasks = [("eng", "HIGH_ROAD")]

    logger.info(f"=== PHASE 1: COMPILATION ===")
    logger.info(f"Targeting {len(tasks)} languages")
    
    valid_langs_map = {}
    phase1_start = time.time()
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(phase_1_verify, t[0], t[1]): t for t in tasks}
        
        for future in concurrent.futures.as_completed(futures):
            code, strategy = futures[future]
            try:
                lang, success, msg = future.result()
                if success:
                    valid_langs_map[lang] = strategy
                    logger.info(f"  [OK] {lang} ({strategy})")
                else:
                    logger.info(f"  [FAIL] {lang}: {msg.splitlines()[0][:100]}...") 
            except Exception as e:
                logger.error(f"  [ERR] Exception for {code}: {e}")

    logger.info(f"Phase 1 complete in {time.time() - phase1_start:.2f}s")
    
    # Enter Phase 2
    phase_2_link(valid_langs_map)
    
    total_duration = time.time() - start_global
    logger.info("\n=== BUILD SUMMARY ===")
    logger.info(f"Total Duration: {total_duration:.2f}s")
    logger.info(f"Languages: {len(valid_langs_map)}/{len(tasks)} compiled")
    
    if len(valid_langs_map) == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()