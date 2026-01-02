# tools/ai_refiner.py
import argparse
import glob
import os
import sys
import time
import textwrap
from pathlib import Path
from typing import Dict, Optional, List
from dotenv import load_dotenv
import google.generativeai as genai

# --- Configuration ---
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
GF_GENERATED_PATH = PROJECT_ROOT / "gf" / "generated" / "src"
GF_CONTRIB_PATH = PROJECT_ROOT / "gf" / "contrib"

# Load Env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = os.getenv("AI_MODEL_NAME", "gemini-1.5-pro")

# System Prompt
SYSTEM_PROMPT = """You are an expert computational linguist specializing in Grammatical Framework (GF).
Your task is to upgrade a "Pidgin" (simplified) grammar implementation into a linguistically accurate one.

The input will be three GF files:
1. Res{Lang}.gf (Resource: Parameters and Types)
2. Syntax{Lang}.gf (Syntax: Clause formation rules)
3. Wiki{Lang}.gf (Concrete: Linearization of AbstractWiki)

The current implementation uses simple string concatenation (String Grammar).
Your goal is to:
1. Introduce proper parameters (e.g., Number, Gender, Case, Politeness) relevant to the language.
2. Update the 'Noun' and 'Verb' types to use inflection tables.
3. Fix the linearization rules in Syntax module to respect the language's grammar.

Output Format:
You must output the full content of the three files, separated by "### FILE: <filename>".
Do not use markdown code blocks. Just raw text with separators.
"""

# --- Logging Helpers ---

def print_header(langs: List[str], dry_run: bool):
    print("========================================")
    print("   AI GRAMMAR REFINER")
    print("========================================")
    print(f"Time:       {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model:      {MODEL_NAME}")
    print(f"Targets:    {', '.join(langs)}")
    print(f"Dry Run:    {'ON' if dry_run else 'OFF'}")
    print(f"Source Dir: {GF_GENERATED_PATH}")
    print(f"Output Dir: {GF_CONTRIB_PATH}")
    print("----------------------------------------")
    sys.stdout.flush()

def log(msg: str, verbose: bool = False, is_verbose_only: bool = False):
    if is_verbose_only and not verbose:
        return
    prefix = "[DEBUG]" if is_verbose_only else "[INFO] "
    print(f"{prefix} {msg}")
    sys.stdout.flush()

# --- Logic ---

def setup_gemini():
    if not GOOGLE_API_KEY:
        print("❌ Error: GOOGLE_API_KEY not found in environment variables.")
        sys.exit(1)
    
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        return genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        print(f"❌ Error initializing AI client: {e}")
        sys.exit(1)

def read_factory_files(iso_code: str, verbose: bool = False) -> Optional[Dict[str, str]]:
    """Reads the generated Tier 3 files for context."""
    # Try exact match first
    target_folder = GF_GENERATED_PATH / iso_code
    
    if not target_folder.exists():
        # Fallback: search case-insensitive
        log(f"Exact folder {iso_code} not found. Searching...", verbose, True)
        for p in GF_GENERATED_PATH.iterdir():
            if p.is_dir() and p.name.lower() == iso_code.lower():
                target_folder = p
                break
        else:
            log(f"❌ Could not find source files for {iso_code}", verbose)
            return None

    files = {}
    # Look for Res, Syntax, Wiki files
    # pattern: *{iso}*.gf or similar. The prompt assumes Res{Lang}.gf
    # We grab all .gf files in the folder to be safe
    gf_files = list(target_folder.glob("*.gf"))
    
    if not gf_files:
        log(f"❌ No .gf files found in {target_folder}", verbose)
        return None

    for fpath in gf_files:
        if fpath.name.startswith("Wiki") or fpath.name.startswith("Res") or fpath.name.startswith("Syntax"):
            try:
                files[fpath.name] = fpath.read_text(encoding="utf-8")
                log(f"   Loaded: {fpath.name}", verbose, True)
            except Exception as e:
                log(f"   Error reading {fpath.name}: {e}", verbose)

    return files

def parse_ai_response(response_text: str) -> Dict[str, str]:
    """Splits the single AI string back into files."""
    files = {}
    current_file = None
    lines = response_text.split('\n')
    buffer = []

    for line in lines:
        if line.strip().startswith("### FILE:"):
            if current_file:
                files[current_file] = "\n".join(buffer)
            current_file = line.replace("### FILE:", "").strip()
            buffer = []
        else:
            buffer.append(line)
            
    if current_file and buffer:
        files[current_file] = "\n".join(buffer)
        
    return files

def refine_language(
    model, 
    iso_code: str, 
    instructions: str, 
    dry_run: bool, 
    verbose: bool
) -> bool:
    log(f"🧠 Refining: {iso_code}...", verbose)
    
    # 1. Load Context
    files = read_factory_files(iso_code, verbose)
    if not files:
        return False
        
    # 2. Build Prompt
    user_prompt = f"Language ISO: {iso_code}\n"
    if instructions:
        user_prompt += f"Instructions: {instructions}\n"
    
    user_prompt += "\n--- EXISTING CODE ---\n"
    for fname, content in files.items():
        user_prompt += f"\n### FILE: {fname}\n{content}\n"
        
    log(f"   Sending {len(files)} files to {MODEL_NAME}...", verbose)
    
    # 3. Call AI
    try:
        start_t = time.time()
        response = model.generate_content(SYSTEM_PROMPT + "\n\n" + user_prompt)
        duration = time.time() - start_t
        log(f"   AI Response received in {duration:.1f}s.", verbose)
        
        refined_files = parse_ai_response(response.text)
        
        if not refined_files:
            log("❌ AI returned invalid format (no ### FILE: markers).", verbose)
            if verbose:
                print("--- Raw Response ---\n" + response.text[:500] + "...\n--------------------")
            return False
            
        # 4. Save
        out_dir = GF_CONTRIB_PATH / iso_code
        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            for fname, content in refined_files.items():
                out_path = out_dir / fname
                out_path.write_text(content.strip(), encoding="utf-8")
                log(f"   💾 Wrote: {out_path}", verbose)
            log(f"✅ Refinement complete for {iso_code}")
        else:
            log(f"   [DRY-RUN] Would write {len(refined_files)} files to {out_dir}", verbose)
            
        return True

    except Exception as e:
        log(f"❌ AI Error: {e}", verbose)
        return False

# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="AI Grammar Refiner (Upgrade Pidgin to Proper GF).")
    
    parser.add_argument("--langs", help="Comma-separated list of ISO codes (e.g. 'zul,xho').")
    parser.add_argument("--instructions", help="Specific linguistic instructions for the AI.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files.")
    parser.add_argument("--verbose", action="store_true", help="Detailed logging.")
    
    # Legacy support
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
         # Assume: python ai_refiner.py <code> <name> [instr]
         print("⚠️  Deprecation Warning: Positional arguments are deprecated. Use --langs.")
         iso = sys.argv[1]
         instr = sys.argv[3] if len(sys.argv) > 3 else ""
         args = argparse.Namespace(langs=iso, instructions=instr, dry_run=False, verbose=True)
    else:
        args = parser.parse_args()

    if not args.langs:
        parser.print_help()
        sys.exit(1)

    targets = [l.strip() for l in args.langs.split(",") if l.strip()]
    
    print_header(targets, args.dry_run)
    
    model = setup_gemini()
    
    success_count = 0
    start_time = time.time()
    
    for lang in targets:
        if refine_language(model, lang, args.instructions, args.dry_run, args.verbose):
            success_count += 1
            
    duration = time.time() - start_time
    
    print("----------------------------------------")
    print(f"Finished in {duration:.2f}s")
    print(f"Success: {success_count}/{len(targets)}")
    print("========================================")

if __name__ == "__main__":
    main()