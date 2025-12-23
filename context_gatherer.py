import os
import pathlib

# --- CONFIGURATION ---
CRITICAL_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "manage.py",
    "diagnostic_check.py",
    "diagnostic_compile_v2.py",
    "debug_engine.py",
    "populate_data.py",
    "app/core/exporters/ud_mapping.py",
    "app/adapters/ninai.py",
    "tools/everything_matrix/build_index.py"
]

RELEVANT_DIRS = [
    "engines", "lexicon", "morphology", "semantics", 
    "constructions", "language_profiles", "utils",
    "gf", "ai_services", "app", "tools"
]

def print_section(title, content):
    print(f"\n{'='*10} {title} {'='*10}")
    print(content)
    print("="*30)

def get_tree_structure(root_path):
    tree_str = ""
    root = pathlib.Path(root_path)
    for path in sorted(root.rglob("*")):
        if any(part.startswith(".") or part in ["__pycache__", "venv", "node_modules", "raw_wikidata", ".git"] for part in path.parts):
            continue
        depth = len(path.relative_to(root).parts)
        if depth > 4: continue
        indent = "  " * (depth - 1)
        tree_str += f"{indent}|- {path.name}\n"
    return tree_str

def main():
    print("--- START CONTEXT DUMP ---")
    print_section("PROJECT STRUCTURE", get_tree_structure("."))
    for fname in CRITICAL_FILES:
        if os.path.exists(fname):
            try:
                with open(fname, "r", encoding="utf-8") as f:
                    content = f.read()
                    if len(content) > 8000: content = content[:4000] + "\n... [TRUNCATED] ...\n" + content[-4000:]
                    print_section(f"FILE: {fname}", content)
            except Exception as e:
                print(f"Could not read {fname}: {e}")
        else:
            print(f"MISSING FILE: {fname}")
    print("\n--- END CONTEXT DUMP ---")
    print("Please COPY EVERYTHING between START and END and paste it back.")

if __name__ == "__main__":
    main()
