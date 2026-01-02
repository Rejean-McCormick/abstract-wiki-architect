# utils/seed_lexicon_ai.py
"""
utils/seed_lexicon_ai.py
------------------------

Bootstraps the lexicon for one or more languages using Generative AI.

Features:
- Generates valid JSON lexicon entries (lemmas, POS, features).
- Supports batch mode (multiple languages).
- Validates and sanitizes AI output before writing.
- Adheres to the Enterprise Standard path: data/lexicon/{iso}/seed.json

Usage:
    python utils/seed_lexicon_ai.py --langs fr,de --verbose
    python utils/seed_lexicon_ai.py --langs zul --limit 20 --dry-run
"""

import argparse
import json
import os
import sys
import time
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

import google.generativeai as genai

# --- Configuration ---
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
LEXICON_DIR = DATA_DIR / "lexicon"

# Load Env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = os.getenv("AI_MODEL_NAME", "gemini-2.0-flash") # Updated default

# System Prompt (Frozen)
SYSTEM_PROMPT = """You are a computational linguist building a lexicon for an Abstract Wikipedia project.
Your task is to generate a JSON lexicon for a specific target language.

Output Format:
Return ONLY valid JSON. The structure must match this schema:
{
  "meta": {
    "language": "<ISO_CODE>",
    "schema_version": 1
  },
  "lemmas": {
    "<lemma_string>": {
      "pos": "NOUN" | "ADJ" | "VERB",
      "gender": "m" | "f" | "n" | "common" (optional),
      "human": true | false (optional),
      "nationality": true (optional, for adjectives like 'French')
    }
  }
}

Task:
Generate {limit} common words used in biographical texts (professions, nationalities, basic verbs).
Include:
- Professions: physicist, writer, teacher, politician, doctor, chemist, actor, etc.
- Nationalities: American, French, German, Chinese, etc.
- Verbs: be, have, born, die, study, win.

Ensure the 'lemma' keys are in the Target Language (not English).
"""

# --- Logging Helpers ---

def print_header(langs: List[str], limit: int, dry_run: bool):
    print("========================================")
    print("   AI LEXICON SEEDER")
    print("========================================")
    print(f"Time:      {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model:     {MODEL_NAME}")
    print(f"Targets:   {', '.join(langs)}")
    print(f"Limit:     {limit} lemmas per language")
    print(f"Dry Run:   {'ON' if dry_run else 'OFF'}")
    print("----------------------------------------")
    sys.stdout.flush()

def log(msg: str, verbose: bool = False, is_verbose_only: bool = False):
    if is_verbose_only and not verbose:
        return
    prefix = "[DEBUG]" if is_verbose_only else "[INFO] "
    print(f"{prefix} {msg}")
    sys.stdout.flush()

# --- Logic ---

def init_ai():
    """Initializes the Google AI client."""
    if not GOOGLE_API_KEY:
        print("❌ Error: GOOGLE_API_KEY not found in environment variables.")
        print("   Please check your .env file.")
        sys.exit(1)
    
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        return genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        print(f"❌ Error initializing AI client: {e}")
        sys.exit(1)

def clean_json_response(text: str) -> str:
    """Strips markdown fences and whitespace."""
    cleaned = text.strip()
    # Remove ```json ... ``` blocks
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    return cleaned.strip()

def validate_and_fix_payload(data: Dict[str, Any], lang_code: str) -> Dict[str, Any]:
    """
    Ensures the payload matches the expected schema.
    Returns a sanitized dictionary.
    """
    if "lemmas" not in data:
        raise ValueError("Missing 'lemmas' key in response.")
    
    # Normalize Meta
    if "meta" not in data:
        data["meta"] = {}
    data["meta"]["language"] = lang_code
    data["meta"]["source"] = "ai_seed"
    data["meta"]["generated_at"] = time.strftime('%Y-%m-%dT%H:%M:%SZ')

    # Normalize Lemmas
    valid_lemmas = {}
    for key, entry in data["lemmas"].items():
        if not key or not isinstance(entry, dict):
            continue
        
        # Enforce minimal fields
        if "pos" not in entry:
            entry["pos"] = "NOUN" # Fallback
            
        # Normalize POS tags
        entry["pos"] = entry["pos"].upper()
        
        valid_lemmas[key] = entry
    
    data["lemmas"] = valid_lemmas
    return data

def seed_language(
    model, 
    lang_code: str, 
    limit: int, 
    dry_run: bool, 
    verbose: bool
) -> bool:
    """Runs the seeding process for a single language."""
    log(f"🌱 Seeding {lang_code}...", verbose)
    
    prompt = SYSTEM_PROMPT.format(limit=limit).replace("<ISO_CODE>", lang_code)
    prompt += f"\nTarget Language Code: {lang_code}"
    
    log(f"Sending prompt ({len(prompt)} chars)...", verbose, is_verbose_only=True)
    if verbose:
        log(f"Prompt Preview: {prompt[:100]}...", verbose, is_verbose_only=True)

    try:
        response = model.generate_content(prompt)
        raw_text = response.text
        
        if verbose:
             log(f"Raw Response ({len(raw_text)} chars). Parsing...", verbose, is_verbose_only=True)

        json_text = clean_json_response(raw_text)
        data = json.loads(json_text)
        
        # Validate
        clean_data = validate_and_fix_payload(data, lang_code)
        count = len(clean_data["lemmas"])
        log(f"   Parsed {count} lemmas.", verbose)

        # Output Path: data/lexicon/{lang}/seed.json
        lang_dir = LEXICON_DIR / lang_code
        output_file = lang_dir / "seed.json"

        if dry_run:
            log(f"   [DRY-RUN] Would write to {output_file}", verbose)
            return True

        # Ensure directory exists
        if not lang_dir.exists():
            log(f"   Creating directory: {lang_dir}", verbose, is_verbose_only=True)
            lang_dir.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(clean_data, f, indent=2, ensure_ascii=False)
        
        log(f"   ✅ Saved to: {output_file}", verbose)
        return True

    except json.JSONDecodeError as e:
        log(f"   ❌ JSON Error: {e}", verbose)
        if verbose:
            print(f"--- Failed Content ---\n{raw_text[:500]}...\n----------------------")
        return False
    except Exception as e:
        log(f"   ❌ API/System Error: {e}", verbose)
        return False

# --- Main ---

def main():
    # 1. Parse Arguments
    parser = argparse.ArgumentParser(description="Seed lexicon data using AI.")
    parser.add_argument("--langs", help="Comma-separated ISO codes (e.g. 'fr,de').")
    parser.add_argument("--limit", type=int, default=50, help="Number of lemmas to generate.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files.")
    parser.add_argument("--verbose", action="store_true", help="Detailed logging.")
    
    # Legacy support detection
    if len(sys.argv) == 3 and not sys.argv[1].startswith("-"):
        # Legacy usage: python script.py <code> <name>
        print("⚠️  Deprecation Warning: Positional arguments are deprecated. Use --langs.")
        args = argparse.Namespace(
            langs=sys.argv[1],
            limit=50,
            dry_run=False,
            verbose=True
        )
    else:
        args = parser.parse_args()

    if not args.langs:
        parser.print_help()
        sys.exit(1)

    targets = [l.strip() for l in args.langs.split(",") if l.strip()]
    
    # 2. Print Header
    print_header(targets, args.limit, args.dry_run)

    # 3. Init AI
    model = init_ai()
    
    # 4. Process
    success_count = 0
    start_time = time.time()
    
    for lang in targets:
        if seed_language(model, lang, args.limit, args.dry_run, args.verbose):
            success_count += 1
            
    duration = time.time() - start_time
    
    # 5. Summary
    print("----------------------------------------")
    print(f"Finished in {duration:.2f}s")
    print(f"Success: {success_count}/{len(targets)}")
    print("========================================")

if __name__ == "__main__":
    main()