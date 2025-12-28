import argparse
import json
import re
import requests
import sys
import logging
from pathlib import Path
from typing import Optional

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION: SINGLE SOURCE OF TRUTH ---
# We use the Everything Matrix to validate if a language is registered in the system.
MATRIX_PATH = Path("data/indices/everything_matrix.json")

# Helper map for CLI convenience (Users type 'en', System needs 'eng')
CLI_INPUT_MAP = {
    "en": "eng", "fr": "fra", "de": "deu", "es": "spa", "it": "ita",
    "nl": "nld", "sv": "swe", "ru": "rus", "bg": "bul", "el": "ell",
    "zh": "zho", "ja": "jpn", "ar": "ara", "hi": "hin"
}

# --- ISO 639-3 to 639-1 MAP (for Storage & Wikidata) ---
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
        # Fallback: If matrix is missing, trust the map or the input if it looks ISO-3
        if len(target_iso) == 3: return target_iso
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

# --- HARVESTER LOGIC ---

RE_ABSTRACT = re.compile(r"fun\s+([^\s:]+).*?--\s*([Q\d]+-?[a-z0-9]*)")
RE_CONCRETE = re.compile(r"lin\s+(\w+)\s*=\s*(.*?)\s*;")
RE_STRING = re.compile(r'"([^"]+)"')

# v2.1 Upgrade: Now fetches Claims (P106/P27) for Semantic Framing
SPARQL_TEMPLATE = """
SELECT ?item ?itemLabel ?itemDescription ?job ?nat WHERE {
  VALUES ?item { %s }
  OPTIONAL { ?item wdt:P106 ?job . }
  OPTIONAL { ?item wdt:P27 ?nat . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "%s". }
}
"""

class GFWordNetHarvester:
    def __init__(self, root_path):
        self.root = Path(root_path)
        self.semantic_map = {} 

    def load_semantics(self):
        path = self.root / "WordNet.gf"
        if not path.exists():
            logger.error(f"❌ Critical: WordNet.gf not found at {path}")
            sys.exit(1)

        logger.info(f"📖 Indexing semantics from {path}...")
        count = 0
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                match = RE_ABSTRACT.search(line)
                if match:
                    func, sem_id = match.groups()
                    self.semantic_map[func.strip()] = sem_id.strip()
                    count += 1
        logger.info(f"   Indexed {count} semantic keys.")

    def harvest_lang(self, rgl_code, iso2_code, out_dir):
        """
        Harvests from the RGL file (using rgl_code e.g. 'Eng') 
        but saves to the storage folder (using iso2_code e.g. 'en').
        """
        # File finding heuristic: WordNetEng.gf
        candidates = [
            f"WordNet{rgl_code.capitalize()}.gf",
            f"WordNet{CLI_INPUT_MAP.get(rgl_code, rgl_code).capitalize()}.gf"
        ]
        
        src_file = None
        for c in candidates:
            if (self.root / c).exists():
                src_file = self.root / c
                break
        
        if not src_file:
            logger.warning(f"⚠️  Skipping {rgl_code}: Could not find WordNet file in {self.root}")
            return

        logger.info(f"🚜 Harvesting {rgl_code} from {src_file.name}...")
        lexicon = {}
        count = 0

        with open(src_file, 'r', encoding='utf-8') as f:
            content = f.read()

        for match in RE_CONCRETE.finditer(content):
            func, rhs = match.groups()
            if "variants {}" in rhs: continue

            strings = RE_STRING.findall(rhs)
            if strings:
                lemma = strings[0]
                sem_id = self.semantic_map.get(func, "")
                
                entry = {"lemma": lemma, "gf_fun": func, "source": "gf-wordnet"}
                if sem_id.startswith("Q"):
                    entry["qid"] = sem_id
                elif sem_id:
                    entry["wnid"] = sem_id

                lexicon[lemma.lower()] = entry
                count += 1

        # SAVE TO ISO-2 FOLDER (Enterprise Standard)
        out_path = Path(out_dir) / iso2_code / "wide.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(lexicon, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Saved {count} words to {out_path}")

class WikidataHarvester:
    def fetch(self, qids, lang_code, domain="people"):
        # Determine Wikidata Language Code (prefer 2-letter if available)
        wd_lang = ISO_3_TO_2.get(lang_code, lang_code)
        
        logger.info(f"☁️  Fetching {len(qids)} items from Wikidata for '{lang_code}' (WD Lang: {wd_lang})...")
        
        # Batch requests if necessary (simple implementation assumes small batch for now)
        values = " ".join([f"wd:{qid}" for qid in qids])
        
        # Construct query with fallback languages
        lang_string = f"{wd_lang},en"
        
        query = SPARQL_TEMPLATE % (values, lang_string)
        
        try:
            r = requests.get(
                "https://query.wikidata.org/sparql", 
                params={'format': 'json', 'query': query}, 
                timeout=30
            )
            r.raise_for_status()
            data = r.json()
            
            results = {}
            for row in data['results']['bindings']:
                qid = row['item']['value'].split('/')[-1]
                if qid not in results:
                    results[qid] = {
                        "lemma": row.get('itemLabel', {}).get('value'),
                        "desc": row.get('itemDescription', {}).get('value', ""),
                        "source": "wikidata-harvester",
                        "domain": domain,
                        "facts": {"P106": [], "P27": []}
                    }
                
                # Aggregate facts
                if 'job' in row:
                    job_qid = row['job']['value'].split('/')[-1]
                    if job_qid not in results[qid]['facts']['P106']:
                        results[qid]['facts']['P106'].append(job_qid)
                        
                if 'nat' in row:
                    nat_qid = row['nat']['value'].split('/')[-1]
                    if nat_qid not in results[qid]['facts']['P27']:
                        results[qid]['facts']['P27'].append(nat_qid)

            return results

        except Exception as e:
            logger.error(f"❌ Wikidata Error: {e}")
            return {}

def main():
    parser = argparse.ArgumentParser(description="Universal Lexicon Harvester (Free/Offline)")
    subparsers = parser.add_subparsers(dest="source", required=True)

    # 1. WordNet (Offline - Uses GF RGL files)
    wn_parser = subparsers.add_parser("wordnet", help="Mine local GF WordNet files")
    wn_parser.add_argument("--root", required=True, help="Path to gf-wordnet folder")
    wn_parser.add_argument("--lang", required=True, help="Target Language (e.g. en, fr)")
    wn_parser.add_argument("--out", default="data/lexicon")

    # 2. Wikidata (Online - Free)
    wd_parser = subparsers.add_parser("wikidata", help="Fetch from Wikidata (Free)")
    wd_parser.add_argument("--lang", required=True, help="Target Language")
    wd_parser.add_argument("--input", required=True, help="JSON file with target QIDs")
    wd_parser.add_argument("--domain", default="people")

    args = parser.parse_args()

    # --- 1. RESOLVE LANGUAGE (RGL Code - 3 Letter) ---
    rgl_code = resolve_and_validate_language(args.lang)
    if not rgl_code:
        print(f"❌ Error: Language '{args.lang}' is not valid or not in the Matrix.")
        sys.exit(1)
        
    # --- 2. DETERMINE STORAGE CODE (ISO Code - 2 Letter) ---
    # We use this for the output directory to ensure persistence matches API standards
    iso2_code = ISO_3_TO_2.get(rgl_code, rgl_code)

    if args.lang != rgl_code:
        print(f"🔧 Resolved Logic:   '{args.lang}' -> '{rgl_code}' (Matrix ID)")
    if rgl_code != iso2_code:
        print(f"📂 Resolved Storage: '{rgl_code}' -> '{iso2_code}' (Data Folder)")

    # --- 3. EXECUTE ---
    if args.source == "wordnet":
        harvester = GFWordNetHarvester(args.root)
        harvester.load_semantics()
        harvester.harvest_lang(rgl_code, iso2_code, args.out)

    elif args.source == "wikidata":
        if not Path(args.input).exists():
             print(f"❌ Input file not found: {args.input}")
             sys.exit(1)
        
        with open(args.input, 'r') as f:
            target_qids = list(json.load(f).keys()) # Assuming input is { "QID": ... }
        
        harvester = WikidataHarvester()
        # Fetch using RGL/Matrix code (internal method handles WD mapping)
        data = harvester.fetch(target_qids, rgl_code, args.domain)
        
        # Save to ISO-2 storage folder
        out_path = Path(f"data/lexicon/{iso2_code}/{args.domain}.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved {len(data)} entries to {out_path}")

if __name__ == "__main__":
    main()