import argparse
import json
import re
import requests
import sys
from pathlib import Path

# --- CONFIGURATION: GF WORDNET ---
# Regex for Root WordNet.gf
RE_ABSTRACT = re.compile(r"fun\s+([^\s:]+).*?--\s*([Q\d]+-?[a-z0-9]*)")
# Regex for Root WordNetEng.gf
RE_CONCRETE = re.compile(r"lin\s+(\w+)\s*=\s*(.*?)\s*;")
RE_STRING = re.compile(r'"([^"]+)"')

# --- CONFIGURATION: WIKIDATA ---
# v2.1 Upgrade: Now fetches Claims (P106/P27) for Semantic Framing
SPARQL_TEMPLATE = """
SELECT ?item ?itemLabel ?itemDescription ?job ?nat WHERE {
  VALUES ?item { %s }
  OPTIONAL { ?item wdt:P106 ?job . }  # Occupation
  OPTIONAL { ?item wdt:P27 ?nat . }   # Citizenship
  SERVICE wikibase:label { bd:serviceParam wikibase:language "%s". }
}
"""

class GFWordNetHarvester:
    def __init__(self, root_path):
        self.root = Path(root_path)
        self.semantic_map = {} 

    def load_semantics(self):
        """Step 1: Index the Abstract Keys (Directly from Root)"""
        path = self.root / "WordNet.gf"
        
        if not path.exists():
            print(f"❌ Critical: WordNet.gf not found at {path}")
            sys.exit(1)

        print(f"📖 Indexing semantics from {path}...")
        count = 0
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                match = RE_ABSTRACT.search(line)
                if match:
                    func, sem_id = match.groups()
                    self.semantic_map[func.strip()] = sem_id.strip()
                    count += 1
        
        print(f"   Indexed {count} semantic keys.")

    def harvest_lang(self, lang_code, out_dir):
        """Step 2: Extract words from Concrete Grammar"""
        fname = f"WordNet{lang_code.capitalize()}.gf"
        src_file = self.root / fname

        if not src_file.exists():
            print(f"⚠️  Skipping {lang_code}: {fname} not found in {self.root}")
            return

        print(f"🚜 Harvesting {lang_code} from {src_file.name}...")
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
                
                entry = {
                    "lemma": lemma,
                    "gf_fun": func,
                    "source": "gf-wordnet"
                }
                
                if sem_id.startswith("Q"):
                    entry["qid"] = sem_id
                elif sem_id:
                    entry["wnid"] = sem_id

                lexicon[lemma.lower()] = entry
                count += 1

        out_path = Path(out_dir) / lang_code / "wide.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(lexicon, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved {count} words to {out_path}")

class WikidataHarvester:
    def fetch(self, qids, lang_code):
        print(f"☁️  Fetching {len(qids)} items (Labels + Facts) from Wikidata for '{lang_code}'...")
        values = " ".join([f"wd:{qid}" for qid in qids])
        query = SPARQL_TEMPLATE % (values, lang_code)
        
        try:
            r = requests.get(
                "https://query.wikidata.org/sparql", 
                params={'format': 'json', 'query': query}, 
                timeout=30
            )
            data = r.json()
            
            # Aggregate Results (One QID can have multiple Jobs/Nationalities)
            results = {}
            for row in data['results']['bindings']:
                qid = row['item']['value'].split('/')[-1]
                
                if qid not in results:
                    results[qid] = {
                        "lemma": row.get('itemLabel', {}).get('value'),
                        "desc": row.get('itemDescription', {}).get('value', ""),
                        "facts": {
                            "P106": set(), # Occupation
                            "P27": set()   # Nationality
                        }
                    }
                
                if 'job' in row:
                    job_qid = row['job']['value'].split('/')[-1]
                    results[qid]['facts']['P106'].add(job_qid)
                    
                if 'nat' in row:
                    nat_qid = row['nat']['value'].split('/')[-1]
                    results[qid]['facts']['P27'].add(nat_qid)

            # Convert sets to lists for JSON serialization
            for qid in results:
                results[qid]['facts']['P106'] = list(results[qid]['facts']['P106'])
                results[qid]['facts']['P27'] = list(results[qid]['facts']['P27'])

            return results

        except Exception as e:
            print(f"❌ Wikidata Error: {e}")
            return {}

def main():
    parser = argparse.ArgumentParser(description="Universal Lexicon Harvester")
    subparsers = parser.add_subparsers(dest="source", required=True)

    wn_parser = subparsers.add_parser("wordnet", help="Mine local GF files")
    wn_parser.add_argument("--root", required=True)
    wn_parser.add_argument("--langs", default="eng")
    wn_parser.add_argument("--out", default="data/lexicon")

    wd_parser = subparsers.add_parser("wikidata", help="Fetch from Cloud")
    wd_parser.add_argument("--lang", required=True)
    wd_parser.add_argument("--input", required=True)
    wd_parser.add_argument("--domain", default="people")

    args = parser.parse_args()

    if args.source == "wordnet":
        harvester = GFWordNetHarvester(args.root)
        harvester.load_semantics()
        for lang in args.langs.split(","):
            harvester.harvest_lang(lang.strip(), args.out)

    elif args.source == "wikidata":
        if not Path(args.input).exists():
             print(f"❌ Input file not found: {args.input}")
             sys.exit(1)
        
        with open(args.input, 'r') as f:
            target_qids = json.load(f).keys()
        
        harvester = WikidataHarvester()
        data = harvester.fetch(target_qids, args.lang)
        
        out_path = Path(f"data/lexicon/{args.lang}/{args.domain}.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved to {out_path}")

if __name__ == "__main__":
    main()