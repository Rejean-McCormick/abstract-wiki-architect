import logging
import re
import os
import sys
import json
import argparse
import time
from typing import Optional, Dict
from pathlib import Path

# Add project root to path if running as script
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import google.generativeai as genai
from app.shared.config import settings
from ai_services.prompts import ARCHITECT_SYSTEM_PROMPT, SURGEON_SYSTEM_PROMPT

# Logger setup
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("architect")

# Constants
PROJECT_ROOT = Path(__file__).parents[1]
MATRIX_PATH = PROJECT_ROOT / "data" / "indices" / "everything_matrix.json"

# [FIX] Point directly to the main GF source folder so 'manage.py build' finds the files automatically
GENERATED_SRC_DIR = PROJECT_ROOT / "gf"

TOPOLOGY_CONFIG = PROJECT_ROOT / "data" / "config" / "topology_weights.json"
# [NEW] Load the mapping configuration for ISO -> RGL codes
ISO_MAP_PATH = PROJECT_ROOT / "data" / "config" / "iso_to_wiki.json"

class ArchitectAgent:
    """
    The AI Agent responsible for writing and fixing GF grammars.
    Acts as the 'Human-in-the-loop' replacement for Tier 3 languages.
    """

    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY
        # [FIX] Use available model from diagnostic
        self.model_name = "gemini-2.0-flash"
        self._client = None
        
        # [NEW] Load RGL Mapping Cache (e.g. zho -> Chi)
        self.iso_to_rgl = self._load_rgl_mapping()

        if self.api_key:
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model_name)
        else:
            logger.warning("⚠️ GOOGLE_API_KEY not found. The Architect Agent is disabled.")

    def _load_rgl_mapping(self) -> Dict[str, str]:
        """Loads the ISO -> RGL Code mapping (e.g. zho -> Chi)."""
        mapping = {}
        if ISO_MAP_PATH.exists():
            try:
                with open(ISO_MAP_PATH, 'r') as f:
                    data = json.load(f)
                    for k, v in data.items():
                        # We map the ISO code (key) to the 'wiki' code (RGL code)
                        if isinstance(v, dict) and "wiki" in v:
                            mapping[k.lower()] = v["wiki"]
            except Exception as e:
                logger.error(f"⚠️ Failed to load ISO map: {e}")
        return mapping

    def get_rgl_code(self, iso_code: str) -> str:
        """Returns the GF-compatible RGL code (e.g. 'Chi') for an ISO code ('zho')."""
        return self.iso_to_rgl.get(iso_code.lower(), iso_code.capitalize())

    def generate_grammar(self, lang_code: str, lang_name: str, topology: str = "SVO") -> Optional[str]:
        """
        Generates a fresh Concrete Grammar (*.gf) for a missing language.
        """
        if not self._client:
            return None

        # [FIX] Determine the correct GF module name (e.g. WikiChi instead of WikiZho)
        rgl_code = self.get_rgl_code(lang_code)
        module_name = f"Wiki{rgl_code}"

        logger.info(f"🏗️  The Architect is designing {lang_name} ({lang_code} -> {module_name}) [Topology: {topology}]...")

        try:
            # Construct the prompt using the Frozen System Prompt
            # [FIX] Skeleton updated to use VP (Standard RGL) instead of VPS (Hallucination)
            user_prompt = f"""
            Act as a Grammatical Framework (GF) expert.
            Write the concrete grammar file '{module_name}.gf' for Language: {lang_name} (ISO: {lang_code}).
            
            # Use this Skeleton EXACTLY:
            concrete {module_name} of AbstractWiki = open Syntax{rgl_code}, Paradigms{rgl_code} in {{
              lincat
                Fact = S ;
                Entity = NP ;
                Predicate = VP ; -- Fixed: Use VP (Verb Phrase), not VPS
              lin
                mkFact s p = mkS (mkCl s p) ;
                -- Implement other linearizations here
            }}
            
            # Constraints
            1. Output ONLY the code.
            2. Do NOT inherit from 'WikiI' or 'Wiki'. Use the 'open' syntax above.
            3. The abstract syntax 'AbstractWiki' defines: 
               cat Fact; Entity; Predicate;
               fun mkFact : Entity -> Predicate -> Fact;
            """
            
            response = self._client.generate_content(
                contents=[
                    {"role": "user", "parts": [ARCHITECT_SYSTEM_PROMPT + "\n\n" + user_prompt]}
                ],
                generation_config={"temperature": 0.1} # Lower temp for strict skeleton following
            )
            
            return self._sanitize_output(response.text, module_name)

        except Exception as e:
            logger.error(f"❌ Architect generation failed for {lang_code}: {e}")
            return None

    def repair_grammar(self, broken_code: str, error_log: str) -> Optional[str]:
        """
        The Surgeon: Patches a broken grammar file based on compiler logs.
        """
        if not self._client:
            return None

        logger.info("🚑 The Surgeon is operating on broken grammar...")

        try:
            user_prompt = f"""
            **BROKEN CODE:**
            {broken_code}

            **COMPILER ERROR:**
            {error_log}
            """

            response = self._client.generate_content(
                contents=[
                    {"role": "user", "parts": [SURGEON_SYSTEM_PROMPT + "\n\n" + user_prompt]}
                ],
                generation_config={"temperature": 0.1}
            )
            
            return self._sanitize_output(response.text)

        except Exception as e:
            logger.error(f"❌ Surgeon repair failed: {e}")
            return None

    def _sanitize_output(self, text: str, module_name: str = "Wiki") -> str:
        """
        Cleans LLM output to ensure only valid GF code remains.
        """
        # 1. Strip markdown fences
        clean = re.sub(r"```(gf)?", "", text)
        clean = clean.strip()
        
        # 2. Ensure it starts with the correct module definition
        if not any(clean.startswith(k) for k in ["concrete", "resource", "interface"]):
            # Try finding the module name provided
            match = re.search(r"(concrete|resource|interface)\s+" + module_name, clean)
            if match:
                clean = clean[match.start():]
            else:
                # Fallback for hallucinated module names
                match = re.search(r"(concrete|resource|interface)\s+Wiki", clean)
                if match:
                    clean = clean[match.start():]
        
        # 3. [FIXED] Robust regex replacement for Abstract Name
        clean = re.sub(r"\bof\s+Wiki\b", "of AbstractWiki", clean)
        
        # 4. [FIXED] Surgical removal of inheritance
        if "= WikiI" in clean or "= Wiki" in clean:
             clean = re.sub(r"=\s*WikiI?\s*(with\s*\([^)]+\))?\s*(\*\*)?", "=", clean)
             
             # If the removal left us without an 'open' keyword, inject it
             if "open" not in clean:
                 clean = clean.replace("=", "= open")

        return clean

# --- CLI Logic (Decoupled Generation) ---

def load_matrix_targets():
    """Loads language metadata from the matrix."""
    if not MATRIX_PATH.exists():
        logger.error(f"Matrix not found at {MATRIX_PATH}. Run 'manage.py build' first.")
        sys.exit(1)
    
    with open(MATRIX_PATH, 'r') as f:
        data = json.load(f)
    return data.get("languages", {})

def save_generated_file(iso: str, code: str, agent: ArchitectAgent):
    """
    Saves the generated code to the correct directory using RGL naming conventions.
    """
    # [FIX] Use the agent to get the correct RGL code for the filename
    rgl_code = agent.get_rgl_code(iso)
    filename = f"Wiki{rgl_code}.gf"
    
    GENERATED_SRC_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GENERATED_SRC_DIR / filename
    
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(code)
    logger.info(f"💾 Saved to: {out_path}")

def get_topology_hint(iso: str) -> str:
    """Tries to find a topology hint from config, defaults to SVO."""
    try:
        if TOPOLOGY_CONFIG.exists():
            with open(TOPOLOGY_CONFIG, 'r') as f:
                data = json.load(f)
                return "SVO"
    except:
        pass
    return "SVO" 

def run_cli():
    parser = argparse.ArgumentParser(description="Abstract Wiki Architect - AI Generator")
    parser.add_argument("--lang", type=str, help="ISO code to generate (e.g. 'zul')")
    parser.add_argument("--missing", action="store_true", help="Generate all missing languages")
    # [NEW] Force flag allows overwriting existing files without manual deletion
    parser.add_argument("--force", action="store_true", help="Overwrite existing grammar files")
    
    args = parser.parse_args()
    
    agent = ArchitectAgent()
    if not agent._client:
        logger.error("❌ Agent disabled (No API Key). Exiting.")
        sys.exit(1)

    targets = load_matrix_targets()

    if args.lang:
        # Single Mode
        iso = args.lang.lower()
        if iso not in targets:
            logger.error(f"❌ Language {iso} not found in Matrix.")
            sys.exit(1)
        
        name = targets[iso].get("meta", {}).get("name", iso)
        code = agent.generate_grammar(iso, name, get_topology_hint(iso))
        if code:
            save_generated_file(iso, code, agent)
            
    elif args.missing:
        logger.info("🔍 Scanning for missing grammars...")
        count = 0
        for iso, meta in targets.items():
            tier = meta.get("meta", {}).get("tier", 3)
            if tier == 1:
                continue

            # [FIX] Check for existence using the Correct RGL filename
            rgl_code = agent.get_rgl_code(iso)
            gen_path = GENERATED_SRC_DIR / f"Wiki{rgl_code}.gf"
            
            # [NEW] Respect the --force flag
            if gen_path.exists() and not args.force:
                continue

            logger.info(f"👉 Missing (or Forcing): {iso}")
            name = meta.get("meta", {}).get("name", iso)
            
            time.sleep(1) 
            
            code = agent.generate_grammar(iso, name, get_topology_hint(iso))
            if code:
                save_generated_file(iso, code, agent)
                count += 1
        
        if count == 0:
            logger.info("✅ No missing languages found.")
    else:
        parser.print_help()

# Global Instance
architect = ArchitectAgent()

if __name__ == "__main__":
    run_cli()