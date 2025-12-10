import requests
import json
import time
import os
from pathlib import Path
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

# Target languages to populate (ISO 639-1 codes)
# Adding the roadmap targets: ko (Korean), da (Danish), fi (Finnish)
TARGET_LANGUAGES = ["ko", "da", "fi"]

# Where to save the shards (Relative to this script)
OUTPUT_DIR = Path("data/lexicon")

# Wikidata SPARQL Endpoint
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# User-Agent is REQUIRED by Wikidata Policy to avoid 403 Forbidden
HEADERS = {
    "User-Agent": "AbstractWikiArchitect/1.0 (mailto:admin@example.com) Python/3.10"
}

# =============================================================================
# CONCEPT MAPPINGS (Abstract Concepts -> Wikidata QIDs)
# =============================================================================

# Domain: People (Professions, Titles)
PEOPLE_CONCEPTS = {
    "Scientist": "Q901",
    "Physicist": "Q169470",
    "Chemist": "Q593644",
    "Biologist": "Q864503",
    "Mathematician": "Q170790",
    "Actor": "Q33999",
    "Writer": "Q36180",
    "Painter": "Q1028181",
    "Poet": "Q49757",
    "Politician": "Q82955",
    "Musician": "Q639669",
    "Teacher": "Q37226",
    "Engineer": "Q81096"
}

# Domain: Science (Disciplines, Objects)
SCIENCE_CONCEPTS = {
    "Physics": "Q413",
    "Chemistry": "Q2329",
    "Biology": "Q420",
    "Mathematics": "Q395",
    "Astronomy": "Q333",
    "Planet": "Q634",
    "Star": "Q523",
    "Atom": "Q9121"
}

# Domain: Core (Function words - HARD TO GET FROM WIKIDATA, placeholder logic)
# Note: Function words usually require manual linguistic rules. 
# We will create a skeleton file for them.

# =============================================================================
# LOGIC
# =============================================================================

def fetch_labels(qids, lang_code):
    """
    Queries Wikidata for the labels of the given QIDs in the target language.
    """
    # Create the VALUES string "wd:Q901 wd:Q169470 ..."
    values_str = " ".join([f"wd:{qid}" for qid in qids])
    
    query = f"""
    SELECT ?item ?itemLabel WHERE {{
      VALUES ?item {{ {values_str} }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{lang_code}". }}
    }}
    """

    try:
        response = requests.get(
            SPARQL_ENDPOINT, 
            params={'query': query, 'format': 'json'},
            headers=HEADERS
        )
        response.raise_for_status()
        data = response.json()
        
        results = {}
        for binding in data["results"]["bindings"]:
            item_url = binding["item"]["value"]
            qid = item_url.split("/")[-1]
            label = binding["itemLabel"]["value"]
            results[qid] = label
            
        return results
        
    except Exception as e:
        print(f"❌ Error fetching data for {lang_code}: {e}")
        return {}

def create_shard(lang_code, domain_name, concept_map):
    """
    Fetches data and writes a V2 Schema JSON shard.
    """
    print(f"   ... Processing domain: {domain_name}")
    
    # 1. Fetch Data
    labels = fetch_labels(list(concept_map.values()), lang_code)
    
    if not labels:
        print(f"      ⚠️ No data found for {domain_name} in {lang_code}")
        return

    # 2. Build Entry Dictionary
    entries = {}
    for concept_key, qid in concept_map.items():
        if qid in labels:
            lemma = labels[qid]
            # Verify we didn't get a QID fallback (Wikidata does this sometimes)
            if lemma == qid: 
                continue
                
            entries[concept_key] = {
                "lemma": lemma,
                "pos": "N",  # Defaulting to Noun for these entity types
                "metadata": {
                    "wikidata_id": qid,
                    "source": "wikidata_automated_import"
                }
            }

    # 3. Create V2 Structure
    shard_data = {
        "_meta": {
            "language": lang_code,
            "domain": domain_name,
            "generated_at": datetime.utcnow().isoformat(),
            "schema_version": "2.0"
        },
        "entries": entries
    }

    # 4. Save File
    lang_dir = OUTPUT_DIR / lang_code
    os.makedirs(lang_dir, exist_ok=True)
    
    filename = f"{domain_name}.json"
    file_path = lang_dir / filename
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(shard_data, f, indent=2, ensure_ascii=False)
        
    print(f"      ✅ Saved {len(entries)} entries to {file_path}")

def create_core_skeleton(lang_code):
    """
    Creates a skeleton core.json since function words (copulas) 
    are hard to query semantically.
    """
    shard_data = {
        "_meta": {
            "language": lang_code,
            "domain": "core",
            "note": "Skeleton created automatically. Please fill manually."
        },
        "entries": {
            "copula": {
                "lemma": "IS", 
                "pos": "V",
                "comment": "Replace IS with actual copula (e.g., est, er, on)"
            }
        }
    }
    
    lang_dir = OUTPUT_DIR / lang_code
    os.makedirs(lang_dir, exist_ok=True)
    
    with open(lang_dir / "core.json", "w", encoding="utf-8") as f:
        json.dump(shard_data, f, indent=2, ensure_ascii=False)
    print(f"      ⚠️ Created skeleton core.json (Requires Manual Edit)")

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    print("🚀 Starting Lexicon Builder (Wikidata -> V2 Shards)")
    print(f"Target Languages: {TARGET_LANGUAGES}")
    print("-" * 60)

    for lang in TARGET_LANGUAGES:
        print(f"\n🌍 Processing Language: [{lang.upper()}]")
        
        # 1. Create People Shard
        create_shard(lang, "people", PEOPLE_CONCEPTS)
        
        # 2. Create Science Shard
        create_shard(lang, "science", SCIENCE_CONCEPTS)
        
        # 3. Create Core Skeleton
        create_core_skeleton(lang)
        
        # Be nice to Wikidata API
        time.sleep(1) 

    print("\n" + "-" * 60)
    print("🎉 Import Complete.")
    print("Next Steps:")
    print("1. Review 'core.json' for each language and add the Copula manually.")
    print("2. Run 'python check_all_languages.py' to verify the load.")

if __name__ == "__main__":
    main()