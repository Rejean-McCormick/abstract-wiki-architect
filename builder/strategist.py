import os
import json
from . import config

def load_json(path, default_type=dict):
    """
    Robust JSON loader. Returns default_type() if file missing/broken.
    """
    if not os.path.exists(path):
        return default_type()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"⚠️  Warning: Corrupt JSON file at {path}")
        return default_type()

def get_build_context(rgl_code):
    """
    Defines ALL dynamic variables available to your strategies.json templates.
    Add new logic here, and it becomes instantly available in the JSON.
    """
    # 1. Determine SimpNP logic based on config
    if config.AMBIGUITY_STRATEGY == "indef":
        simp_np_val = "mkNP a_Det cn"
    else:
        simp_np_val = "mkNP cn"

    # 2. Return the Context Dictionary
    return {
        "code": rgl_code,
        "simp_np": simp_np_val,
        # Future-proofing: Add more vars here if needed (e.g. "author": "Gemini")
    }

def generate_blueprint(rgl_code, modules, strategies):
    """
    Evaluates a language against the list of strategies using generic templating.
    """
    available_modules = set(modules.keys())
    context = get_build_context(rgl_code)

    for strat in strategies:
        required = set(strat.get("requirements", []))
        
        # Check if requirements are a subset of available modules
        if required.issubset(available_modules):
            
            # --- MATCH FOUND ---
            blueprint = {
                "status": strat["name"],
                "imports": [],
                "lincats": {},
                "rules": {}
            }

            try:
                # 1. Expand Imports
                # Uses .format() to replace {code}, {simp_np}, etc.
                blueprint["imports"] = [
                    imp.format(**context) for imp in strat.get("imports", [])
                ]

                # 2. Expand Lincats (Qualified Names)
                base = strat.get("lincat_base", "").format(**context)
                blueprint["lincats"] = {
                    "Phr": f"{base}.Phr",
                    "NP":  f"{base}.NP",
                    "CN":  f"{base}.CN",
                    "Adv": f"{base}.Adv"
                }

                # 3. Expand Rules
                for key, template in strat.get("rules", {}).items():
                    blueprint["rules"][key] = template.format(**context)

                return blueprint

            except KeyError as e:
                print(f"❌ Template Error in Strategy '{strat['name']}': Missing variable {e}")
                continue

    return {"status": "SKIP", "imports": [], "lincats": {}, "rules": {}}

def generate_plan():
    print("🧠 Strategist: Calculating optimal build paths (Template-Driven)...")
    
    # Load inputs (inventory is dict, strategies is list)
    inventory_data = load_json(config.RGL_INVENTORY_FILE, dict)
    inventory = inventory_data.get("languages", {})
    strategies = load_json(config.STRATEGIES_FILE, list)
    
    if not inventory:
        print(f"❌ Inventory missing or empty: {config.RGL_INVENTORY_FILE}")
        return False
    if not strategies:
        print(f"❌ Strategies missing or empty: {config.STRATEGIES_FILE}")
        return False

    build_plan = {}
    stats = {s["name"]: 0 for s in strategies}
    stats["SKIP"] = 0

    for rgl_code, data in inventory.items():
        modules = data.get("modules", {})
        
        blueprint = generate_blueprint(rgl_code, modules, strategies)
        
        if blueprint["status"] != "SKIP":
            build_plan[rgl_code] = blueprint
        
        # Safe stat counting
        st = blueprint.get("status", "SKIP")
        stats[st] = stats.get(st, 0) + 1

    # Save Plan
    plan_path = os.path.join("builder", "build_plan.json")
    try:
        with open(plan_path, 'w', encoding='utf-8') as f:
            json.dump(build_plan, f, indent=2)
        
        print(f"   📋 Plan saved to {plan_path}")
        print(f"   Stats: {json.dumps(stats)}")
        return True
    except IOError as e:
        print(f"❌ Error writing build plan: {e}")
        return False