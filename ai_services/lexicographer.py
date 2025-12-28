import json
import logging
import math
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Try importing the client, handling both module and script execution contexts
try:
    from . import client
except ImportError:
    try:
        import ai_services.client as client
    except ImportError:
        # Fallback for dev environments without the full package installed
        print("⚠️ Warning: Could not import 'ai_services.client'. AI features will be mocked.")
        class MockClient:
            def generate(self, prompt): return "{}"
        client = MockClient()

# Setup Logger
logger = logging.getLogger("ai_services.lexicographer")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- CONFIGURATION: SINGLE SOURCE OF TRUTH ---
# We use the Everything Matrix to validate if a language is registered in the system.
MATRIX_PATH = Path("data/indices/everything_matrix.json")

# Helper map for CLI convenience (Users type 'en', System needs 'eng')
# This bridges the gap without needing a separate file.
CLI_INPUT_MAP = {
    "en": "eng", "fr": "fra", "de": "deu", "es": "spa", "it": "ita",
    "nl": "nld", "sv": "swe", "ru": "rus", "bg": "bul", "el": "ell",
    "zh": "zho", "ja": "jpn", "ar": "ara", "hi": "hin"
}

# --- ISO 639-3 to 639-1 MAP (for Storage) ---
# Enterprise Standard: Persistence Layer (Zone B) uses 2-letter codes.
ISO_3_TO_2 = {v: k for k, v in CLI_INPUT_MAP.items()}

def resolve_and_validate_language(input_code: str) -> Optional[str]:
    """
    1. Normalizes input (en -> eng).
    2. Checks if 'eng' exists in the Everything Matrix.
    3. Returns the valid ISO 639-3 code (Logic ID) or None.
    """
    # 1. Normalize Input
    clean_code = input_code.lower().strip()
    target_iso = CLI_INPUT_MAP.get(clean_code, clean_code)

    # 2. Load Matrix
    if not MATRIX_PATH.exists():
        logger.error(f"❌ Critical: Everything Matrix not found at {MATRIX_PATH}")
        return None

    try:
        with open(MATRIX_PATH, "r", encoding="utf-8") as f:
            matrix = json.load(f)
            
        registered_languages = matrix.get("languages", {})

        # 3. Validate
        if target_iso in registered_languages:
            return target_iso
        
        # Helper: Check if maybe it matches a folder name (e.g. "french")
        for iso, data in registered_languages.items():
            folder = data.get("meta", {}).get("folder", "")
            if folder == clean_code:
                return iso

        logger.error(f"❌ Language '{target_iso}' is not registered in Everything Matrix.")
        return None

    except Exception as e:
        logger.error(f"❌ Failed to read Everything Matrix: {e}")
        return None

# --- SEED CONCEPTS ---
DOMAINS = {
    "core": [
        "the", "a", "this", "that", 
        "is", "was", "has", "had", 
        "he", "she", "it", "they", 
        "person", "thing", "water", "fire", "good", "bad", "big", "small"
    ],
    "geography": [
        "country", "city", "river", "mountain", "ocean",
        "France", "Germany", "United States", "Japan", "China",
        "Paris", "Berlin", "London", "Tokyo", "New York"
    ],
    "science": [
        "physics", "chemistry", "biology", "mathematics",
        "atom", "molecule", "energy", "force", "gravity",
        "scientist", "theory", "experiment", "laboratory"
    ]
}

def _clean_json_response(response_text):
    """
    Helper to extract raw JSON from potential markdown wrapping.
    """
    if not response_text:
        return None
    
    clean_text = response_text.strip()
    
    if clean_text.startswith("```"):
        first_newline = clean_text.find("\n")
        if first_newline != -1:
            clean_text = clean_text[first_newline+1:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
    return clean_text.strip()

def generate_lexicon(words: List[str], lang_code: str, batch_size=20) -> Dict:
    """
    Generates JSON Lexicon Data for a list of English concepts.
    """
    if not words or not lang_code:
        return {}

    full_lexicon = {}
    total_batches = math.ceil(len(words) / batch_size)
    
    logger.info(f"📖 Lexicographer: Processing {len(words)} words in {total_batches} batches for {lang_code}...")

    for i in range(total_batches):
        batch = words[i * batch_size : (i + 1) * batch_size]
        
        # PROMPT: Request JSON Data Schema compatible with Lexicon Store
        prompt = f"""
        Act as an expert computational linguist.
        
        TASK: Translate these English concepts into {lang_code} (ISO 639-3).
        
        INPUT CONCEPTS:
        {", ".join(batch)}
        
        OUTPUT SCHEMA (Strict JSON):
        {{
            "english_concept": {{
                "lemma": "translation",
                "pos": "NOUN/VERB/ADJ/PN",
                "gender": "m/f/n" (optional)
            }}
        }}
        
        EXAMPLE OUTPUT for French:
        {{
            "apple": {{ "lemma": "pomme", "pos": "NOUN", "gender": "f" }},
            "good": {{ "lemma": "bon", "pos": "ADJ" }}
        }}
        
        INSTRUCTIONS:
        1. Return ONLY the JSON object.
        2. Ensure valid JSON syntax.
        """
        
        try:
            response = client.generate(prompt)
            clean_json = _clean_json_response(response)
            
            if clean_json:
                batch_result = json.loads(clean_json)
                if isinstance(batch_result, dict):
                    # Tag source
                    for k, v in batch_result.items():
                        if isinstance(v, dict):
                            v["source"] = "ai-lexicographer"
                            
                    full_lexicon.update(batch_result)
                    logger.info(f"   Batch {i+1}/{total_batches}: Retrieved {len(batch_result)} entries.")
                else:
                    logger.warning(f"   Batch {i+1} failed: Expected dict, got {type(batch_result)}.")
            else:
                logger.warning(f"   Batch {i+1} returned empty response.")
                
        except json.JSONDecodeError as e:
            logger.error(f"   Batch {i+1} JSON Error: {e}")
        except Exception as e:
            logger.error(f"   Batch {i+1} Client Error: {e}")

    return full_lexicon

def main():
    parser = argparse.ArgumentParser(description="AI Lexicographer Agent (Zone B)")
    parser.add_argument("--lang", required=True, help="Target Language (e.g. 'en', 'fra')")
    parser.add_argument("--domain", required=True, choices=list(DOMAINS.keys()), help="Semantic Domain to generate")
    
    args = parser.parse_args()
    
    # 1. Resolve Language against Everything Matrix
    rgl_code = resolve_and_validate_language(args.lang)
    
    if not rgl_code:
        print(f"❌ Error: Language '{args.lang}' is not valid or not registered in the Everything Matrix.")
        print("   Run 'tools/everything_matrix/build_index.py' if you recently added it.")
        sys.exit(1)
            
    # 2. Determine Storage Path (ISO 2-letter)
    iso2_code = ISO_3_TO_2.get(rgl_code, rgl_code)

    if args.lang != rgl_code:
        print(f"🔧 Resolved Logic:   '{args.lang}' -> '{rgl_code}' (Matrix ID)")
    if rgl_code != iso2_code:
        print(f"📂 Resolved Storage: '{rgl_code}' -> '{iso2_code}' (Data Folder)")
        
    # 3. Select Words
    target_words = DOMAINS[args.domain]
    
    # 4. Generate
    result = generate_lexicon(target_words, rgl_code)
    
    # 5. Save to Disk (ISO 2-letter folder)
    output_dir = Path(f"data/lexicon/{iso2_code}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"{args.domain}.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        
    print(f"✅ Saved {len(result)} entries to {output_path}")

if __name__ == "__main__":
    main()