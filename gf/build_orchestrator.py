import os
import json
import subprocess
import sys
import shutil
import glob
import concurrent.futures
import multiprocessing
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# ===========================================================================
# CONFIGURATION
# ===========================================================================

# Paths
GF_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = GF_DIR.parent
MATRIX_PATH = PROJECT_ROOT / "data" / "indices" / "everything_matrix.json"
GENERATED_SRC_DIR = PROJECT_ROOT / "gf" / "generated" / "src"
BUILD_LOGS_DIR = GF_DIR / "build_logs"
PGF_OUTPUT_FILE = GF_DIR / "AbstractWiki.pgf"
ABSTRACT_NAME = "AbstractWiki"
CONFIG_DIR = PROJECT_ROOT / "data" / "config"

# Add Project Root to Path for Imports
sys.path.append(str(PROJECT_ROOT))

# Optional: Weighted Topology Factory (Tier 3 Generation)
try:
    from utils.grammar_factory import GrammarFactory
    HAS_FACTORY = True
except ImportError:
    HAS_FACTORY = False

# Logging Colors
class Colors:
    INFO = "\033[94m"
    SUCCESS = "\033[92m"
    WARN = "\033[93m"
    ERROR = "\033[91m"
    RESET = "\033[0m"

def log(level: str, msg: str):
    c = getattr(Colors, level, Colors.RESET)
    print(f"{c}[{level}] {msg}{Colors.RESET}")

# ===========================================================================
# 1. CORE LOGIC (Picklable for Parallel Execution)
# ===========================================================================

def generate_abstract_and_interface():
    """Generates the core Abstract grammar files."""
    # 1. Abstract
    abs_path = GF_DIR / f"{ABSTRACT_NAME}.gf"
    log("INFO", f"Generating Abstract Grammar: {abs_path}")
    abs_content = f"""abstract {ABSTRACT_NAME} = {{
  cat Entity; Property; Fact; Predicate; Modifier; Value;
  fun
    mkFact : Entity -> Predicate -> Fact;
    mkIsAProperty : Entity -> Property -> Fact;
    FactWithMod : Fact -> Modifier -> Fact;
    mkLiteral : Value -> Entity;
    Entity2NP : Entity -> Entity; Property2AP : Property -> Property; VP2Predicate : Predicate -> Predicate;
}}\n"""
    with open(abs_path, 'w', encoding='utf-8') as f: f.write(abs_content)

    # 2. Interface
    iface_path = GF_DIR / "WikiI.gf"
    log("INFO", f"Generating Interface Grammar: {iface_path}")
    iface_content = f"""incomplete concrete WikiI of {ABSTRACT_NAME} = open Syntax in {{
  lincat Entity = NP; Property = AP; Fact = S; Predicate = VP; Modifier = Adv; Value = {{s : Str}};
  lin
    mkFact s p = mkS (mkCl s p);
    mkIsAProperty s p = mkS (mkCl s (mkVP p));
    FactWithMod f m = mkS m f;
    Entity2NP x = x; Property2AP x = x; VP2Predicate x = x;
    mkLiteral v = mkNP (mkN v.s); 
}}\n"""
    with open(iface_path, 'w', encoding='utf-8') as f: f.write(iface_content)

def get_rgl_base() -> Optional[Path]:
    """Resolves the location of the RGL library."""
    # 1. Env Var Override
    env_path = os.environ.get("GF_LIB_PATH")
    if env_path and os.path.exists(env_path):
        return Path(env_path) / "src"
    
    # 2. Local Project Sibling
    internal_path = PROJECT_ROOT / "gf-rgl"
    if internal_path.exists():
        return internal_path / "src"
        
    return None

def resolve_paths(iso: str, meta: Dict, rgl_base: Optional[Path]) -> Tuple[Optional[Path], List[str]]:
    """Finds the source file and include paths for a language."""
    paths = [str(GF_DIR), "."]
    
    # Add RGL paths if available
    if rgl_base:
        paths.extend([
            str(rgl_base),
            str(rgl_base / "api"),
            str(rgl_base / "prelude"),
            str(rgl_base / "abstract"),
            str(rgl_base / "common")
        ])

    suffix = iso.capitalize()
    target_file = f"Wiki{suffix}.gf"

    # Strategy A: Check Contrib (Manual Overrides)
    contrib_path = GF_DIR / "contrib" / iso / target_file
    if contrib_path.exists():
        paths.append(str(contrib_path.parent))
        return contrib_path, paths

    # Strategy B: Check Generated (Factory/AI)
    gen_path = GENERATED_SRC_DIR / iso.lower() / target_file
    if gen_path.exists():
        paths.append(str(gen_path.parent))
        return gen_path, paths

    # Strategy C: Dynamic RGL Discovery
    if rgl_base and "folder" in meta:
        rgl_folder = rgl_base / meta["folder"]
        if rgl_folder.exists():
            # 1. Detect actual RGL suffix (e.g. 'Fre' vs 'Fra')
            # Look for Syntax*.gf
            candidates = list(rgl_folder.glob("Syntax*.gf"))
            if candidates:
                # e.g., SyntaxFre.gf -> Fre
                detected_suffix = candidates[0].stem.replace("Syntax", "")
                
                # 2. Generate Connector if missing
                connector_path = GF_DIR / f"Wiki{detected_suffix}.gf"
                if not connector_path.exists():
                    with open(connector_path, 'w') as f:
                        f.write(f"concrete Wiki{detected_suffix} of {ABSTRACT_NAME} = WikiI ** open Syntax{detected_suffix}, Paradigms{detected_suffix} in {{}};\n")
                
                paths.append(str(rgl_folder))
                return connector_path, paths

    return None, paths

def attempt_factory_generation(iso: str, meta: Dict) -> bool:
    """
    Tier 3 Fallback: Uses Weighted Topology Factory to generate a valid grammar.
    Replaces the old AI call with a deterministic, local generator.
    """
    if not HAS_FACTORY:
        return False
        
    try:
        # Check if we have topology data
        topo_file = CONFIG_DIR / "topology_weights.json"
        if not topo_file.exists():
            return False

        # Init Factory
        factory = GrammarFactory(weights_path=str(topo_file))
        
        # Determine Order (default SVO)
        order = meta.get("blocks", {}).get("topology", "SVO")
        
        # Generate Code
        code = factory.create_concrete(iso, order)
        
        # Save
        out_dir = GENERATED_SRC_DIR / iso.lower()
        out_dir.mkdir(parents=True, exist_ok=True)
        
        suffix = iso.capitalize()
        with open(out_dir / f"Wiki{suffix}.gf", 'w') as f:
            f.write(code)
            
        return True
    except Exception as e:
        # Silent fail is acceptable here; main loop will catch "file not found"
        return False

def verify_single_language(args):
    """
    Worker Function: Compiles one language in isolation to check validity.
    Returns: (iso_code, file_path_str, success_bool)
    """
    iso, meta, rgl_base_str = args
    rgl_base = Path(rgl_base_str) if rgl_base_str else None
    
    # 1. Resolve or Generate
    file_path, include_paths = resolve_paths(iso, meta, rgl_base)
    
    if not file_path:
        # Try Factory Generation
        if attempt_factory_generation(iso, meta):
            file_path, include_paths = resolve_paths(iso, meta, rgl_base)
    
    if not file_path:
        return iso, None, False

    # 2. Prepare Command
    # Use -batch -c (Check only)
    # Deduplicate paths
    unique_paths = list(dict.fromkeys(include_paths))
    path_arg = os.pathsep.join(unique_paths)
    
    cmd = ["gf", "-batch", "-c", "-path", path_arg, str(file_path)]
    
    try:
        # Run Verification
        result = subprocess.run(
            cmd, 
            cwd=str(GF_DIR), 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        if result.returncode == 0:
            return iso, str(file_path), True
        else:
            # Log failure to file for the Surgeon to pick up later
            err_log = BUILD_LOGS_DIR / f"{iso}_error.log"
            with open(err_log, 'w') as f:
                f.write(result.stderr)
            return iso, str(file_path), False
            
    except Exception as e:
        return iso, None, False

# ===========================================================================
# 2. ORCHESTRATOR MAIN
# ===========================================================================

def main():
    log("INFO", "🚀 Abstract Wiki Architect v2.0: Parallel Orchestrator Online")
    
    # 1. Environment Prep
    if BUILD_LOGS_DIR.exists(): shutil.rmtree(BUILD_LOGS_DIR)
    BUILD_LOGS_DIR.mkdir(parents=True)
    
    if not MATRIX_PATH.exists():
        log("ERROR", f"Matrix not found at {MATRIX_PATH}. Run 'build_index.py' first.")
        sys.exit(1)
        
    with open(MATRIX_PATH, 'r') as f:
        matrix = json.load(f)
    
    # Filter active targets
    targets = {
        k: v for k, v in matrix.get("languages", {}).items() 
        if v.get("status", {}).get("build_strategy") != "SKIP"
    }
    
    log("INFO", f"Matrix Loaded: {len(targets)} active targets.")

    # 2. Generate Core Files
    generate_abstract_and_interface()
    
    # 3. Verify Abstract
    log("INFO", "Verifying Abstract Syntax...")
    try:
        subprocess.run(["gf", "-batch", "-c", "AbstractWiki.gf"], check=True, cwd=str(GF_DIR))
    except subprocess.CalledProcessError:
        log("ERROR", "Fatal: AbstractWiki.gf failed to compile.")
        sys.exit(1)

    # 4. Parallel Verification Loop
    rgl_base = get_rgl_base()
    rgl_base_str = str(rgl_base) if rgl_base else None
    
    # Prepare Arguments for Worker
    worker_args = [(iso, meta, rgl_base_str) for iso, meta in targets.items()]
    
    valid_files = []
    
    log("INFO", f"⚡ Verifying {len(targets)} languages in parallel...")
    
    # Use CPU count for workers
    max_workers = multiprocessing.cpu_count()
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(verify_single_language, worker_args))
        
    # 5. Process Results
    for iso, path, success in results:
        if success:
            log("SUCCESS", f"✅ {iso}")
            valid_files.append(path)
        else:
            if path:
                log("ERROR", f"❌ {iso}: Compilation Failed (See logs)")
            else:
                log("WARN", f"⚠️  {iso}: Source not found (Skipped)")

    if not valid_files:
        log("ERROR", "No languages survived verification. Aborting link.")
        sys.exit(1)

    # 6. Single-Shot Linking (The "Last Man Standing" Fix)
    log("INFO", "---------------------------------------------------")
    log("INFO", f"🔗 Linking {len(valid_files)} languages into PGF binary...")
    
    # We must construct the path argument again for the final link
    # This is a bit redundant but ensures the Linker sees everything
    all_paths = [str(GF_DIR), "."]
    if rgl_base:
        all_paths.append(str(rgl_base))
        # Add subfolders recursively or explicitly
        all_paths.extend([str(p.parent) for p in [Path(f) for f in valid_files]])
    
    # Dedupe
    final_path_arg = os.pathsep.join(list(dict.fromkeys(all_paths)))
    
    link_cmd = [
        "gf", 
        "-batch", 
        "-make",
        "-path", final_path_arg,
        "--name", ABSTRACT_NAME,  # Force internal name
        "AbstractWiki.gf"
    ] + valid_files
    
    try:
        subprocess.run(link_cmd, check=True, cwd=str(GF_DIR))
        
        # Cleanup artifacts
        generated_pgf = GF_DIR / f"{ABSTRACT_NAME}.pgf"
        if generated_pgf.exists():
            # If output is different name, rename/move
            if generated_pgf != PGF_OUTPUT_FILE:
                shutil.move(generated_pgf, PGF_OUTPUT_FILE)
            log("SUCCESS", f"📦 Binary Created: {PGF_OUTPUT_FILE}")
        else:
            log("ERROR", "Binary file missing after success return code?")
            
    except subprocess.CalledProcessError as e:
        log("ERROR", f"Linking Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()