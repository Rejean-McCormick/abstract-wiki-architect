import json
import os
import subprocess
import sys
import re

CONFIG_PATH = 'config/everything_matrix_config.json'
FAILURE_REPORT = 'data/reports/build_failures.json'

ABSTRACT_WIKI = """
abstract Wiki = {
  flags startcat = Phr ;
  cat
    Phr ; NP ; CN ; Adv ;
  fun
    SimpNP : CN -> NP ;
    John : NP ;
    Here : Adv ;
    apple_N : CN ;
}
"""

def load_config():
    if not os.path.exists(CONFIG_PATH): return None
    with open(CONFIG_PATH, 'r') as f: return json.load(f)

def generate_concrete(wiki_code, data):
    rgl_code = data["rgl_code"]
    mode = data["strategy"]
    wiki_mod = f"Wiki{wiki_code}"
    
    if mode == "HIGH_ROAD":
        imports = [f"Grammar{rgl_code}", f"Paradigms{rgl_code}"]
        content = f"""
concrete {wiki_mod} of Wiki = {", ".join(imports)} ** open Syntax{rgl_code}, (P = {imports[-1]}) in {{
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}}
"""
    elif mode == "SAFE_MODE":
        imports = [f"Cat{rgl_code}", f"Noun{rgl_code}", f"Paradigms{rgl_code}"]
        content = f"""
concrete {wiki_mod} of Wiki = {", ".join(imports[:-1])} ** open {imports[1]}, (P = {imports[-1]}) in {{
  lin
    SimpNP cn = MassNP cn ;
    John = UsePN (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = UseN (P.mkN "apple") ;
}}
"""
    else: return None

    filename = f"{wiki_mod}.gf"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content.strip())
    return filename

def build():
    config = load_config()
    if not config: return

    rgl_base = config.get("rgl_base_path", "gf-rgl/src")
    strategy_file = config.get("strategy_json", "data/reports/rgl_matrix_strategy.json")
    inventory_file = config.get("inventory_file", "data/indices/rgl_inventory.json")
    
    with open(strategy_file, 'r') as f: strategy_map = json.load(f)
    with open(inventory_file, 'r') as f: family_folders = json.load(f).get("families", [])

    print(f"🔨 Preparing build for {len(strategy_map)} languages...")

    # 1. Generate Abstract
    with open("Wiki.gf", "w", encoding="utf-8") as f: f.write(ABSTRACT_WIKI)
    
    # 2. Prepare Paths
    include_paths = {rgl_base, os.path.join(rgl_base, 'api'), os.path.join(rgl_base, 'abstract'), 
                     os.path.join(rgl_base, 'common'), os.path.join(rgl_base, 'prelude')}
    for data in strategy_map.values():
        if data.get("path_root"): include_paths.add(data["path_root"])
    for family in family_folders:
        include_paths.add(os.path.join(rgl_base, family))
    path_arg = ":".join(include_paths)

    # 3. SELF-HEALING COMPILE LOOP
    active_languages = {k: v for k, v in strategy_map.items() if v["strategy"] in ["HIGH_ROAD", "SAFE_MODE"]}
    failed_languages = {} # Store failures here
    
    attempt = 1
    max_attempts = 15

    while attempt <= max_attempts:
        print(f"\n🚀 Compilation Attempt #{attempt} ({len(active_languages)} languages)...")

        gf_files = ["Wiki.gf"]
        for code, data in active_languages.items():
            fname = generate_concrete(code, data)
            if fname: gf_files.append(fname)

        cmd = ["gf", "-make", "-path", path_arg] + gf_files
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("\n🏆 SUCCESS: Wiki.pgf created successfully!")
                break
            else:
                output = result.stderr + result.stdout
                print(f"💥 Compilation failed.")
                
                # Regex Analysis
                culprit_code = None
                reason = "Unknown Error"

                # Case A: Missing dependency (File GrammarX.gf does not exist)
                missing_match = re.search(r"File (Grammar|Syntax|Cat|Noun|Paradigms)([A-Z][a-z]{2,3})\.gf does not exist", output)
                if missing_match:
                    culprit_rgl = missing_match.group(2)
                    reason = f"Missing dependency: {missing_match.group(0)}"
                    for w_code, data in active_languages.items():
                        if data["rgl_code"] == culprit_rgl:
                            culprit_code = w_code
                            break
                
                # Case B: Syntax error in generated file (WikiX.gf:...)
                if not culprit_code:
                    concrete_match = re.search(r"Wiki([A-Z][a-z]{2,3})\.gf:", output)
                    if concrete_match:
                        culprit_code = concrete_match.group(1)
                        reason = "Syntax error in concrete grammar"

                # Handle Culprit
                if culprit_code and culprit_code in active_languages:
                    print(f"   🗑️  Removing {culprit_code}. Reason: {reason}")
                    failed_languages[culprit_code] = {
                        "reason": reason,
                        "strategy": active_languages[culprit_code]["strategy"]
                    }
                    del active_languages[culprit_code]
                else:
                    print("   ❌ Could not identify specific culprit. Aborting to avoid infinite loop.")
                    # Force break, write what we have
                    break

        except Exception as e:
            print(f"   ❌ Critical System Error: {e}")
            break
        
        attempt += 1

    # 4. REPORT FAILURES
    os.makedirs(os.path.dirname(FAILURE_REPORT), exist_ok=True)
    with open(FAILURE_REPORT, 'w') as f:
        json.dump(failed_languages, f, indent=2)
    print(f"📝 Failure report saved to {FAILURE_REPORT}")

if __name__ == "__main__":
    build()