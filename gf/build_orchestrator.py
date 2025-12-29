# gf/build_orchestrator.py
import os
import subprocess
import sys
import json
import logging
import concurrent.futures
from pathlib import Path

# --- Imports ---
# Allow importing from sibling/parent directories
sys.path.append(str(Path(__file__).parent.parent))
try:
    from utils.grammar_factory import generate_safe_mode_grammar
except ImportError:
    generate_safe_mode_grammar = None

# --- Setup ---
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("Orchestrator")

ROOT_DIR = Path(__file__).parent.parent
GF_DIR = ROOT_DIR / "gf"
RGL_SRC = ROOT_DIR / "gf-rgl" / "src"
RGL_API = RGL_SRC / "api"  # <--- CRITICAL FIX: Add API path for Syntax.gf
GENERATED_SRC = ROOT_DIR / "generated" / "src"
LOG_DIR = GF_DIR / "build_logs"
MATRIX_FILE = ROOT_DIR / "data" / "indices" / "everything_matrix.json"

# Ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_SRC.mkdir(parents=True, exist_ok=True)

def load_matrix():
    if not MATRIX_FILE.exists():
        logger.warning("⚠️  Everything Matrix not found. Defaulting to empty.")
        return {}
    try:
        with open(MATRIX_FILE) as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error("❌ Corrupt Everything Matrix. Cannot proceed.")
        return {}

def ensure_source_exists(lang_code, strategy):
    """
    Ensures the .gf source file exists before compilation.
    If strategy is SAFE_MODE, it triggers the Factory/Architect Agent.
    """
    # HIGH_ROAD (Tier 1) assumes files exist in gf/ or are linked RGL files
    if strategy == "HIGH_ROAD":
        return True
    
    # SAFE_MODE (Tier 3) requires generation
    target_file = GENERATED_SRC / f"Wiki{lang_code.title()}.gf"
    
    if not target_file.exists():
        logger.info(f"🔨 Generating grammar for {lang_code} (Factory)...")
        if generate_safe_mode_grammar:
            try:
                code = generate_safe_mode_grammar(lang_code)
                with open(target_file, "w") as f:
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
    gf_filename = f"Wiki{lang_code.title()}.gf"
    
    # Determine Source Path based on Strategy
    if strategy == "SAFE_MODE":
        # Factory files live in generated/src
        file_path = GENERATED_SRC / gf_filename
    else:
        # High Road files live in gf/ (manual or rgl wrappers)
        file_path = GF_DIR / gf_filename

    # Build the Path Arguments
    # CRITICAL: Must include RGL_SRC (for langs), RGL_API (for Syntax), and GENERATED
    path_args = f"{RGL_SRC}:{RGL_API}:{GENERATED_SRC}:."
    
    cmd = ["gf", "-batch", "-path", path_args, "-c", str(file_path)]
    
    # Execute Compiler
    proc = subprocess.run(cmd, cwd=str(GF_DIR), capture_output=True, text=True)
    
    # Log errors if failed
    if proc.returncode != 0:
        # Log to file for archival
        with open(LOG_DIR / f"Wiki{lang_code.title()}.log", "w") as f:
            f.write(proc.stderr + "\n" + proc.stdout)
            
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
    
    # --- VERBOSE FIX: Capture the actual error message ---
    error_msg = proc.stderr.strip()
    if not error_msg:
        # Sometimes GF prints errors to stdout
        error_msg = proc.stdout.strip()
    if not error_msg:
        error_msg = f"Unknown Error (Exit Code {proc.returncode})"
        
    return (lang_code, False, error_msg)

def phase_2_link(valid_langs_map):
    """
    Phase 2: Link all valid .gfo files into a single AbstractWiki.pgf binary.
    """
    if not valid_langs_map:
        logger.error("❌ No valid languages to link! Build aborted.")
        sys.exit(1)

    # Build the list of concrete grammars to link
    # We must point GF to the source file location for the linker to find the .gfo
    targets = []
    for code, strategy in valid_langs_map.items():
        lang_name = f"Wiki{code.title()}.gf"
        
        if strategy == "SAFE_MODE":
            # Point to generated folder
            targets.append(str(GENERATED_SRC / lang_name))
        else:
            # Point to local GF folder
            targets.append(lang_name)

    path_args = f"{RGL_SRC}:{RGL_API}:{GENERATED_SRC}:."
    
    # We link against AbstractWiki.gf
    cmd = ["gf", "-make", "-path", path_args, "-name", "AbstractWiki", "AbstractWiki.gf"] + targets

    logger.info(f"🔗 Linking {len(targets)} languages into PGF binary...")
    proc = subprocess.run(cmd, cwd=str(GF_DIR), capture_output=True, text=True)

    if proc.returncode == 0:
        logger.info("✅ BUILD SUCCESS: AbstractWiki.pgf created.")
    else:
        logger.error(f"❌ LINK FAILED:\n{proc.stderr}")

def main():
    matrix = load_matrix()
    tasks = []
    
    # 1. Parse The Matrix v2.1 (Verdict Driven)
    if matrix:
        for code, data in matrix.get("languages", {}).items():
            # v2.1: Read the 'verdict' object
            verdict = data.get("verdict", {})
            strategy = verdict.get("build_strategy", "SKIP")
            
            if strategy in ["HIGH_ROAD", "SAFE_MODE"]:
                tasks.append((code, strategy))
    else:
        # Fallback for bootstrapping
        logger.info("⚠️  Matrix empty. Using bootstrap defaults.")
        tasks = [("eng", "HIGH_ROAD")]

    logger.info(f"🏗️  Phase 1: Verifying {len(tasks)} languages...")
    
    # 2. Execute Phase 1 (Parallel Compilation)
    valid_langs_map = {}
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(phase_1_verify, t[0], t[1]): t for t in tasks}
        


        for future in concurrent.futures.as_completed(futures):
            code, strategy = futures[future]
            try:
                lang, success, msg = future.result()
                if success:
                    valid_langs_map[lang] = strategy
                    print(f"  [+] {lang}: OK ({strategy})")
                else:
                    print(f"  [-] {lang}: FAILED")
                    # FIX: Print the FULL error message to diagnose issues
                    print(f"      {msg}") 
            except Exception as e:
                logger.error(f"  [!] Exception for {code}: {e}")

    # 3. Execute Phase 2 (Linking)
    phase_2_link(valid_langs_map)

if __name__ == "__main__":
    main()