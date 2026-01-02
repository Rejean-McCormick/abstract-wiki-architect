# tools/harvest_lexicon.py
import argparse
import json
import re
import requests
import sys
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Tuple, List, Any

# --- CONFIGURATION: SINGLE SOURCE OF TRUTH ---
BASE_DIR = Path(__file__).resolve().parent.parent

# Prefer repo-root config if present, otherwise data/config (matches codedump reality)
ISO_MAP_CANDIDATES = [
    BASE_DIR / "config" / "iso_to_wiki.json",
    BASE_DIR / "data" / "config" / "iso_to_wiki.json",
]
# [FIX] Use correct relative path for matrix
MATRIX_PATH = BASE_DIR / "data" / "indices" / "everything_matrix.json"

# Global Maps (Populated on Startup)
ISO2_TO_RGL: Dict[str, str] = {}  # 'en' -> 'Eng'
RGL_TO_ISO2: Dict[str, str] = {}  # 'Eng' -> 'en'

# Setup Logger (configured in main for stdout)
logger = logging.getLogger(__name__)

HARVESTER_VERSION = "harvester/2.2"


def _find_iso_map_path() -> Path:
    for p in ISO_MAP_CANDIDATES:
        if p.exists():
            return p
    # fall back to the canonical (data/config) for error message clarity
    return ISO_MAP_CANDIDATES[-1]


def load_iso_map() -> None:
    """
    Loads the Central Chart (iso_to_wiki.json) to build language mappings.
    This replaces hardcoded dictionaries and ensures sync with the Engine.
    """
    config_path = _find_iso_map_path()
    logger.info(f"Loading ISO map from: {config_path}")
    
    if not config_path.exists():
        logger.error(f"❌ Critical: Config file missing (tried: {', '.join(map(str, ISO_MAP_CANDIDATES))})")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for iso_code, value in data.items():
            # Only ISO-2 keys should populate ISO2_TO_RGL
            if len(iso_code) != 2:
                continue

            # Handle v1 (string) and v2 (object) formats
            rgl_full = value.get("wiki") if isinstance(value, dict) else value
            if not isinstance(rgl_full, str) or not rgl_full:
                continue

            # Normalize 'WikiEng' -> 'Eng' for internal consistency
            rgl_suffix = rgl_full.replace("Wiki", "")

            ISO2_TO_RGL[iso_code] = rgl_suffix
            RGL_TO_ISO2[rgl_suffix] = iso_code
            # Also map the full name just in case 'WikiEng' is passed
            RGL_TO_ISO2[rgl_full] = iso_code
            count += 1

        logger.info(f"✅ Loaded {count} ISO-2 entries")

    except Exception as e:
        logger.error(f"❌ Failed to parse language config: {e}")
        sys.exit(1)


def resolve_and_validate_language(input_code: str) -> Optional[Tuple[str, str]]:
    """
    Resolves any input (en, eng, WikiEng) to the canonical pair (RGL_Suffix, ISO2).
    Returns: (rgl_code, iso2_code) e.g., ('Eng', 'en')
    """
    clean = (input_code or "").strip()
    if not clean:
        logger.error("❌ Empty language code.")
        return None

    # Normalize common shapes
    clean_norm = clean.lower()
    clean_suffix = clean.replace("Wiki", "").replace("wiki", "")
    clean_suffix_cap = clean_suffix[:1].upper() + clean_suffix[1:] if clean_suffix else clean_suffix

    # 1) ISO-2 code? (e.g., 'en')
    if clean_norm in ISO2_TO_RGL:
        return ISO2_TO_RGL[clean_norm], clean_norm

    # 2) RGL suffix? (e.g., 'Eng') ...
    if clean_suffix in RGL_TO_ISO2:
        return clean_suffix, RGL_TO_ISO2[clean_suffix]
    if clean_suffix_cap in RGL_TO_ISO2:
        return clean_suffix_cap, RGL_TO_ISO2[clean_suffix_cap]

    # 3) Fallback: Matrix Validation (matrix keys are ISO-2)
    if MATRIX_PATH.exists():
        try:
            with open(MATRIX_PATH, "r", encoding="utf-8") as f:
                matrix = json.load(f)
            langs = matrix.get("languages", {})

            if clean_norm in langs:
                # Valid ISO-2 but missing in iso_to_wiki.json
                return clean_norm.capitalize(), clean_norm
        except Exception:
            pass

    logger.error(f"❌ Language '{input_code}' is not recognized in system configuration.")
    return None


# --- HARVESTER LOGIC ---

RE_ABSTRACT = re.compile(r"fun\s+([^\s:]+).*?--\s*([Q\d]+-?[a-z0-9]*)")
RE_CONCRETE = re.compile(r"lin\s+(\w+)\s*=\s*(.*?)\s*;")
RE_STRING = re.compile(r'"([^"]+)"')

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
        # [FIX] Ensure Path object handles OS separators correctly
        self.root = Path(root_path)
        self.semantic_map = {}

    def load_semantics(self):
        path = self.root / "WordNet.gf"
        if not path.exists():
            logger.error(f"❌ Critical: WordNet.gf not found at {path}")
            sys.exit(1)

        logger.info(f"📖 Indexing semantics from {path}...")
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                match = RE_ABSTRACT.search(line)
                if match:
                    func, sem_id = match.groups()
                    self.semantic_map[func.strip()] = sem_id.strip()
                    count += 1
        logger.info(f"    Indexed {count} semantic keys.")

    def harvest_lang(self, rgl_code, iso2_code, out_dir):
        """
        Harvests from the RGL file (using rgl_code e.g. 'Eng')
        but saves to the storage folder (using iso2_code e.g. 'en').
        """
        candidates = [
            f"WordNet{rgl_code}.gf",
            f"WordNet{rgl_code.capitalize()}.gf",
        ]

        src_file = None
        # [FIX] Recursive glob to find nested language files
        for c in candidates:
            found = list(self.root.rglob(c))
            if found:
                src_file = found[0]
                break

        if not src_file:
            logger.warning(f"⚠️  Skipping {rgl_code}: Could not find WordNet file in {self.root}")
            return

        logger.info(f"🚜 Harvesting {rgl_code} from {src_file.name}...")
        lexicon = {}
        count = 0

        with open(src_file, "r", encoding="utf-8") as f:
            content = f.read()

        for match in RE_CONCRETE.finditer(content):
            func, rhs = match.groups()
            if "variants {}" in rhs:
                continue

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

        # [FIX] Use Path join for OS independence
        out_path = Path(out_dir) / iso2_code / "wide.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(lexicon, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Saved {count} words to {out_path}")
        return count


class WikidataHarvester:
    def _http_post_with_retry(self, url: str, params: Dict[str, Any], headers: Dict[str, str], max_retries: int = 3) -> Optional[Dict[str, Any]]:
        backoff = 1
        for attempt in range(1, max_retries + 1):
            try:
                r = requests.get(url, params=params, headers=headers, timeout=30)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                logger.warning(f"  ⚠️ Attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error(f"  ❌ Failed after {max_retries} attempts.")
                    return None
        return None

    def fetch(self, qids: List[str], iso2_code: str, domain: str = "people") -> Dict[str, Any]:
        logger.info(f"☁️  Fetching {len(qids)} items from Wikidata for '{iso2_code}'...")

        chunk_size = 50
        all_results = {}
        total_chunks = (len(qids) + chunk_size - 1) // chunk_size

        for i in range(0, len(qids), chunk_size):
            chunk = qids[i : i + chunk_size]
            chunk_idx = (i // chunk_size) + 1
            
            logger.info(f"  Processing chunk {chunk_idx}/{total_chunks} ({len(chunk)} items)...")
            
            values = " ".join([f"wd:{qid}" for qid in chunk])
            lang_string = f"{iso2_code},en"
            query = SPARQL_TEMPLATE % (values, lang_string)

            data = self._http_post_with_retry(
                "https://query.wikidata.org/sparql",
                params={"format": "json", "query": query},
                headers={"User-Agent": "AbstractWikiArchitect/2.2"},
            )

            if not data:
                continue

            bindings = data.get("results", {}).get("bindings", [])
            for row in bindings:
                try:
                    qid = row["item"]["value"].split("/")[-1]
                    if qid not in all_results:
                        all_results[qid] = {
                            "lemma": row.get("itemLabel", {}).get("value"),
                            "desc": row.get("itemDescription", {}).get("value", ""),
                            "source": "wikidata-harvester",
                            "domain": domain,
                            "facts": {"P106": [], "P27": []},
                        }

                    if "job" in row:
                        job_qid = row["job"]["value"].split("/")[-1]
                        if job_qid not in all_results[qid]["facts"]["P106"]:
                            all_results[qid]["facts"]["P106"].append(job_qid)

                    if "nat" in row:
                        nat_qid = row["nat"]["value"].split("/")[-1]
                        if nat_qid not in all_results[qid]["facts"]["P27"]:
                            all_results[qid]["facts"]["P27"].append(nat_qid)
                except KeyError:
                    pass

        return all_results


def main():
    # 1. Configure logging to stdout for GUI compatibility
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout, force=True)
    start_time = time.time()
    
    print(f"=== LEXICON HARVESTER ({HARVESTER_VERSION}) ===")
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print("-" * 40)
    
    load_iso_map()

    parser = argparse.ArgumentParser(description="Universal Lexicon Harvester (Free/Offline)")
    subparsers = parser.add_subparsers(dest="source", required=True)

    wn_parser = subparsers.add_parser("wordnet", help="Mine local GF WordNet files")
    wn_parser.add_argument("--root", required=True, help="Path to gf-wordnet folder")
    wn_parser.add_argument("--lang", required=True, help="Target Language (e.g. en, fr)")
    # [FIX] Default path using platform-agnostic join
    wn_parser.add_argument("--out", default=str(Path("data") / "lexicon"))

    wd_parser = subparsers.add_parser("wikidata", help="Fetch from Wikidata (Free)")
    wd_parser.add_argument("--lang", required=True, help="Target Language (e.g. en, fr)")
    wd_parser.add_argument("--input", required=True, help="JSON file with target QIDs")
    wd_parser.add_argument("--domain", default="people")

    args = parser.parse_args()

    resolved = resolve_and_validate_language(args.lang)
    if not resolved:
        sys.exit(1)

    rgl_code, iso2_code = resolved
    logger.info(f"🔧 Target: RGL='{rgl_code}' | ISO='{iso2_code}'")

    entries_count = 0
    output_file = ""

    if args.source == "wordnet":
        harvester = GFWordNetHarvester(args.root)
        harvester.load_semantics()
        entries_count = harvester.harvest_lang(rgl_code, iso2_code, args.out)
        output_file = str(Path(args.out) / iso2_code / "wide.json")

    elif args.source == "wikidata":
        input_path = Path(args.input)
        if not input_path.exists():
            logger.error(f"❌ Input file not found: {args.input}")
            sys.exit(1)

        with open(input_path, "r", encoding="utf-8") as f:
            raw_input = json.load(f)
            target_qids = raw_input if isinstance(raw_input, list) else list(raw_input.keys())

        harvester = WikidataHarvester()
        data = harvester.fetch(target_qids, iso2_code, args.domain)
        entries_count = len(data)

        out_path = Path(f"data/lexicon/{iso2_code}/{args.domain}.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        output_file = str(out_path)

        logger.info(f"✅ Saved {entries_count} entries")

    duration = time.time() - start_time
    
    print("\n=== SUMMARY ===")
    print(f"Language: {iso2_code}")
    print(f"Source:   {args.source}")
    print(f"Entries:  {entries_count}")
    print(f"Output:   {output_file}")
    print(f"Duration: {duration:.2f}s")


if __name__ == "__main__":
    main()