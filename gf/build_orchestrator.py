import os
import json
import subprocess
import sys
import shutil
from typing import List, Dict, Tuple, Optional

# v2.0 Integration
try:
    from ai_services.architect import architect
except ImportError:
    architect = None  # Graceful fallback if AI deps missing

# ===========================================================================
# CONFIGURATION
# ===========================================================================

GF_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(GF_DIR)
MATRIX_PATH = os.path.join(PROJECT_ROOT, "data", "indices", "everything_matrix.json")
GENERATED_SRC_DIR = os.path.join(PROJECT_ROOT, "gf", "generated", "src")
BUILD_LOGS_DIR = os.path.join(GF_DIR, "build_logs")
PGF_OUTPUT_FILE = os.path.join(GF_DIR, "AbstractWiki.pgf")
ABSTRACT_NAME = "AbstractWiki"

# Fallback mapping if Matrix is incomplete
CODE_TO_NAME_FALLBACK = {
    "zul": "Zulu", "yor": "Yoruba", "ibo": "Igbo", "hau": "Hausa", 
    "wol": "Wolof", "kin": "Kinyarwanda"
}

# ===========================================================================
# MATRIX LOADER (v2.0 Data-Driven Build)
# ===========================================================================

def load_build_targets() -> Dict[str, Dict]:
    """
    Loads the target languages from the 'Everything Matrix'.
    """
    if not os.path.exists(MATRIX_PATH):
        print(f"❌ Critical: Matrix not found at {MATRIX_PATH}")
        print("   Run 'tools/everything_matrix/build_index.py' first.")
        sys.exit(1)
        
    with open(MATRIX_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Filter for active/safe languages
    targets = {}
    for code, entry in data.items():
        # In v2.0, we try to build everything that isn't explicitly broken
        if entry.get("status", {}).get("build_strategy") != "BROKEN":
            targets[code] = entry
            
    return targets

def get_gf_suffix(iso_code: str, name_map: Dict = {}) -> str:
    # Use standard 3-letter capitalization (e.g. Zul) unless RGL differs
    return iso_code.capitalize()

# ===========================================================================
# GENERATORS (Abstract & Interface)
# ===========================================================================

def generate_abstract():
    filename = f"{ABSTRACT_NAME}.gf"
    # Core Abstract Syntax v2.0
    content = f"""abstract {ABSTRACT_NAME} = {{
  cat Entity; Property; Fact; Predicate; Modifier; Value;
  fun
    mkFact : Entity -> Predicate -> Fact;
    mkIsAProperty : Entity -> Property -> Fact;
    FactWithMod : Fact -> Modifier -> Fact;
    mkLiteral : Value -> Entity;
    Entity2NP : Entity -> Entity; Property2AP : Property -> Property; VP2Predicate : Predicate -> Predicate;
    
    -- Lexicon Stubs (Filled by RGL or AI)
    lex_animal_N : Entity; 
    lex_walk_V : Predicate; 
    lex_blue_A : Property;
}}\n"""
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f: 
        f.write(content)
    return filename

def generate_interface():
    filename = "WikiI.gf"
    content = f"""incomplete concrete WikiI of {ABSTRACT_NAME} = open Syntax in {{
  lincat Entity = NP; Property = AP; Fact = S; Predicate = VP; Modifier = Adv; Value = {{s : Str}};
  lin
    mkFact s p = mkS (mkCl s p);
    mkIsAProperty s p = mkS (mkCl s (mkVP p));
    FactWithMod f m = mkS m f;
    Entity2NP x = x; Property2AP x = x; VP2Predicate x = x;
}}\n"""
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f: 
        f.write(content)
    return filename

# ===========================================================================
# PATH RESOLUTION
# ===========================================================================

def resolve_language_path(iso_code: str, rgl_src_base: str) -> Tuple[Optional[str], Optional[List[str]]]:
    """
    Locates the .gf source file.
    Checks: 1. Contrib -> 2. Generated (Factory) -> 3. RGL (Official)
    """
    suffix = get_gf_suffix(iso_code)
    target_file = f"Wiki{suffix}.gf"
    
    contrib_base = os.path.join(GF_DIR, "contrib")
    
    # Paths to include in GF search path
    paths = [GF_DIR, "."] 

    if rgl_src_base:
        paths.extend([
            rgl_src_base, 
            os.path.join(rgl_src_base, "api"), 
            os.path.join(rgl_src_base, "prelude"), 
            os.path.join(rgl_src_base, "abstract"), 
            os.path.join(rgl_src_base, "common")
        ])

    # 1. Contrib (Manual Overrides)
    contrib_path = os.path.join(contrib_base, iso_code, target_file)
    if os.path.exists(contrib_path):
        paths.append(os.path.dirname(contrib_path))
        return contrib_path, paths

    # 2. Generated (AI / Factory)
    folder = iso_code.lower() 
    factory_path = os.path.join(GENERATED_SRC_DIR, folder, target_file)
    if os.path.exists(factory_path):
        paths.append(os.path.dirname(factory_path))
        return factory_path, paths
        
    # 3. RGL (Official)
    # We rely on the Everything Matrix or manual mapping to find the RGL folder name
    # For now, we assume standard folder structure if not found above
    if rgl_src_base:
        # Simple scan of RGL directory for the language folder
        # This is a heuristic; robust lookup uses the Matrix 'rgl_path'
        candidate_rgl = os.path.join(rgl_src_base, iso_code.lower()) # e.g. .../english
        # But RGL uses full names (english, french). 
        # In v2.0, we rely on the Matrix to tell us we are safe, 
        # or we rely on the Factory to have generated a bridge.
        pass

    return None, None

def get_rgl_base() -> Optional[str]:
    """Finds the GF Resource Grammar Library path."""
    rgl_base = os.environ.get("GF_LIB_PATH")
    if not rgl_base:
        possible_paths = [
            "/usr/share/x86_64-linux-ghc-9.6.7/gf-3.12.0/lib",
            "/usr/local/lib/gf", 
            "/usr/lib/gf",
        ]
        for p in possible_paths:
            if os.path.exists(p): rgl_base = p; break
    
    if rgl_base and os.path.exists(os.path.join(rgl_base, "src")):
        return os.path.join(rgl_base, "src")
    return rgl_base

# ===========================================================================
# AI INTERVENTION (The Architect & Surgeon)
# ===========================================================================

def attempt_ai_generation(iso_code: str, lang_meta: Dict) -> bool:
    """
    Calls The Architect to generate a grammar from scratch.
    """
    if not architect:
        return False

    lang_name = lang_meta.get("name", CODE_TO_NAME_FALLBACK.get(iso_code, iso_code))
    print(f"🏗️ Architect: Designing grammar for {lang_name} ({iso_code})...")
    
    code_content = architect.generate_grammar(iso_code, lang_name)
    if not code_content:
        return False

    # Save to Generated Source
    suffix = get_gf_suffix(iso_code)
    folder = os.path.join(GENERATED_SRC_DIR, iso_code.lower())
    os.makedirs(folder, exist_ok=True)
    
    filepath = os.path.join(folder, f"Wiki{suffix}.gf")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code_content)
        
    print(f"✅ Architect: Blueprint saved to {filepath}")
    return True

def attempt_ai_repair(iso_code: str, filepath: str, error_log: str) -> bool:
    """
    Calls The Surgeon to fix a compilation error.
    """
    if not architect:
        return False
        
    print(f"🚑 Surgeon: Attempting repair on {iso_code}...")
    
    with open(filepath, "r", encoding="utf-8") as f:
        broken_code = f.read()
        
    fixed_code = architect.repair_grammar(broken_code, error_log)
    if not fixed_code:
        print("💀 Surgeon: Patient died on the table.")
        return False
        
    # Backup original
    shutil.copy(filepath, filepath + ".bak")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(fixed_code)
        
    print(f"🩹 Surgeon: Patch applied to {filepath}")
    return True

# ===========================================================================
# MAIN ORCHESTRATOR
# ===========================================================================

def main():
    print("🚀 Abstract Wiki Architect v2.0: Orchestrator Online")
    
    # 0. Setup
    if os.path.exists(BUILD_LOGS_DIR): shutil.rmtree(BUILD_LOGS_DIR)
    os.makedirs(BUILD_LOGS_DIR)
    
    # 1. Load Matrix
    targets = load_build_targets()
    print(f"[*] Matrix loaded: {len(targets)} build targets.")

    # 2. Compile Abstract
    generate_abstract()
    generate_interface()
    
    env = os.environ.copy()
    rgl_base = get_rgl_base()
    
    try:
        subprocess.run(["gf", "-batch", "-c", "AbstractWiki.gf"], 
                      check=True, cwd=GF_DIR, env=env)
    except subprocess.CalledProcessError:
        print("❌ Fatal: Abstract compilation failed.")
        sys.exit(1)

    valid_files = []
    all_paths = []
    
    # 3. Process Languages
    for iso, meta in targets.items():
        file_path, paths = resolve_language_path(iso, rgl_base)
        
        # PHASE 1.5: Architect Generation
        if not file_path:
            # If missing, try to generate it via AI
            if attempt_ai_generation(iso, meta):
                # Re-resolve after generation
                file_path, paths = resolve_language_path(iso, rgl_base)
        
        if not file_path:
            # Still missing? Skip.
            continue
            
        # Ensure imports resolve
        deduped_paths = list(dict.fromkeys([GF_DIR] + paths))
        path_arg = os.pathsep.join(deduped_paths)
        
        # PHASE 1: Verify (Compile)
        cmd = ["gf", "-batch", "-c", "-path", path_arg, file_path]
        
        result = subprocess.run(
            cmd, cwd=GF_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        if result.returncode == 0:
            print(f"✅ {iso}: Verified")
            valid_files.append(file_path)
            all_paths.extend(deduped_paths)
        else:
            # PHASE 1.5: Surgeon Repair
            print(f"❌ {iso}: Compilation Failed. Invoking Surgeon...")
            if attempt_ai_repair(iso, file_path, result.stderr):
                # Retry Compilation Once
                retry_result = subprocess.run(
                    cmd, cwd=GF_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if retry_result.returncode == 0:
                    print(f"✅ {iso}: Repaired & Verified")
                    valid_files.append(file_path)
                    all_paths.extend(deduped_paths)
                else:
                    print(f"💀 {iso}: Repair failed. See logs.")
                    with open(os.path.join(BUILD_LOGS_DIR, f"{iso}_error.log"), "w") as f:
                        f.write(retry_result.stderr)
            else:
                with open(os.path.join(BUILD_LOGS_DIR, f"{iso}_error.log"), "w") as f:
                    f.write(result.stderr)

    # 4. PHASE 2: Link
    if not valid_files:
        print("❌ No languages to link.")
        sys.exit(1)
        
    print(f"\n🔗 Linking {len(valid_files)} languages...")
    final_paths = list(dict.fromkeys(all_paths))
    path_arg = os.pathsep.join(final_paths)
    
    build_cmd = ["gf", "-batch", "-make", "-path", path_arg, "AbstractWiki.gf"] + valid_files
    
    try:
        subprocess.run(build_cmd, check=True, cwd=GF_DIR, env=env)
        
        # Move output if needed
        generated_pgf = os.path.join(GF_DIR, f"{ABSTRACT_NAME}.pgf")
        if os.path.exists(generated_pgf) and generated_pgf != PGF_OUTPUT_FILE:
             shutil.move(generated_pgf, PGF_OUTPUT_FILE)
             
        print(f"📦 SUCCESS! Binary created at: {PGF_OUTPUT_FILE}")
        
    except subprocess.CalledProcessError:
        print("❌ Linking Failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()