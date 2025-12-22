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
GENERATED_SRC_DIR = PROJECT_ROOT / "gf" / "generated" / "src"
TOPOLOGY_CONFIG = PROJECT_ROOT / "data" / "config" / "topology_weights.json"

class ArchitectAgent:
    """
    The AI Agent responsible for writing and fixing GF grammars.
    Acts as the 'Human-in-the-loop' replacement for Tier 3 languages.
    """

    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY
        self.model_name = settings.AI_MODEL_NAME
        self._client = None

        if self.api_key:
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model_name)
        else:
            logger.warning("⚠️ GOOGLE_API_KEY not found. The Architect Agent is disabled.")

    def generate_grammar(self, lang_code: str, lang_name: str, topology: str = "SVO") -> Optional[str]:
        """
        Generates a fresh Concrete Grammar (*.gf) for a missing language.
        
        Args:
            lang_code: ISO 3-letter code (e.g., 'zul').
            lang_name: English name (e.g., 'Zulu').
            topology: Basic word order hint (SVO, SOV, VSO).
            
        Returns:
            Raw GF source code string, or None if disabled/failed.
        """
        if not self._client:
            return None

        logger.info(f"🏗️  The Architect is designing {lang_name} ({lang_code}) [Topology: {topology}]...")

        try:
            # Construct the prompt using the Frozen System Prompt
            user_prompt = f"""
            Write the concrete grammar for Language: {lang_name} (Code: {lang_code}).
            Constraint: The basic word order is {topology}.
            """
            
            response = self._client.generate_content(
                contents=[
                    {"role": "user", "parts": [ARCHITECT_SYSTEM_PROMPT + "\n\n" + user_prompt]}
                ],
                generation_config={"temperature": 0.2} # Low temp for deterministic code
            )
            
            return self._sanitize_output(response.text)

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

    def _sanitize_output(self, text: str) -> str:
        """
        Cleans LLM output to ensure only valid GF code remains.
        Removes Markdown code blocks (```gf ... ```).
        """
        # Strip markdown fences
        clean = re.sub(r"```(gf)?", "", text)
        clean = clean.strip()
        
        # Ensure it starts with concrete/resource/interface
        if not any(clean.startswith(k) for k in ["concrete", "resource", "interface"]):
            # Fallback: Try to find the start of the code
            match = re.search(r"(concrete|resource|interface)\s+Wiki", clean)
            if match:
                clean = clean[match.start():]
                
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

def save_generated_file(iso: str, code: str):
    """Saves the generated code to the correct directory."""
    suffix = iso.capitalize()
    out_dir = GENERATED_SRC_DIR / iso.lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    
    out_path = out_dir / f"Wiki{suffix}.gf"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(code)
    logger.info(f"💾 Saved to: {out_path}")

def get_topology_hint(iso: str) -> str:
    """Tries to find a topology hint, defaults to SVO."""
    # This is a stub. In reality, we could look up the 'topology_weights.json' or matrix meta.
    return "SVO" 

def run_cli():
    parser = argparse.ArgumentParser(description="Abstract Wiki Architect - AI Generator")
    parser.add_argument("--lang", type=str, help="ISO code to generate (e.g. 'zul')")
    parser.add_argument("--missing", action="store_true", help="Generate all missing languages")
    
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
        
        name = targets[iso].get("meta", {}).get("name", iso) # Fallback name
        code = agent.generate_grammar(iso, name, get_topology_hint(iso))
        if code:
            save_generated_file(iso, code)
            
    elif args.missing:
        # Batch Mode
        logger.info("🔍 Scanning for missing grammars...")
        count = 0
        for iso, meta in targets.items():
            # Check if source exists
            path = meta.get("paths", {}).get("source")
            if path and os.path.exists(path):
                continue # Exists
            
            # Also check if we already generated it but didn't index it yet
            gen_path = GENERATED_SRC_DIR / iso / f"Wiki{iso.capitalize()}.gf"
            if gen_path.exists():
                continue

            logger.info(f"👉 Missing: {iso}")
            name = meta.get("meta", {}).get("name", iso)
            
            # Rate limit handling (naive)
            time.sleep(1) 
            
            code = agent.generate_grammar(iso, name, get_topology_hint(iso))
            if code:
                save_generated_file(iso, code)
                count += 1
        
        if count == 0:
            logger.info("✅ No missing languages found.")
    else:
        parser.print_help()

# Global Instance (for import compatibility if needed)
architect = ArchitectAgent()

if __name__ == "__main__":
    run_cli()