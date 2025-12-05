import os
import re

# Mapping of file paths to the specific symbols to remove
TASKS = {
    "morphology/celtic.py": {"List"},
    "morphology/indo_aryan.py": {"Optional", "List"},
    "morphology/iranic.py": {"Optional"},
    "morphology/romance.py": {"Optional"},
    "morphology/slavic.py": {"List"},
    "qa/test_frames_entity.py": {"Dict"},
    "qa/test_frames_narrative.py": {"pytest"},
    "qa/test_frames_relational.py": {"Location", "semantics.types.Location"},
    "qa_tools/batch_test_generator.py": {"Dict", "Any"},
    "semantics/all_frames.py": {"Iterable", "MutableMapping", "Union"},
    "semantics/common/location.py": {"Dict"},
    "semantics/common/roles.py": {"Mapping"},
    "semantics/entity/law_treaty_policy_frame.py": {"TimeSpan", "semantics.types.TimeSpan"},
}

def clean_file(file_path, unused_symbols):
    if not os.path.exists(file_path):
        print(f"Skipping {file_path} (File not found)")
        return

    print(f"Cleaning {file_path}...")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # 1. Handle "from module import A, B, C"
        # Regex captures: Group 1="from X import ", Group 2="A, B, C"
        from_import_match = re.match(r'^(from\s+[\w\.]+\s+import\s+)(.+)$', stripped)
        
        if from_import_match:
            prefix = from_import_match.group(1)
            imports_part = from_import_match.group(2)
            
            # Remove comments from the import line if present
            comment = ""
            if "#" in imports_part:
                split_comment = imports_part.split("#", 1)
                imports_part = split_comment[0]
                comment = "  #" + split_comment[1]

            # Split by comma and clean up whitespace/parentheses
            # We treat multi-line parenthesis imports as single lines here for simplicity 
            # (assuming standard black formatting put them on one line or this script runs before formatting)
            current_imports = [i.strip().replace("(", "").replace(")", "") for i in imports_part.split(",")]
            
            # Filter out the unused symbols
            kept_imports = [i for i in current_imports if i and i.split(" as ")[0] not in unused_symbols]

            if not kept_imports:
                # If no imports remain, skip adding this line (it deletes the line)
                continue
            else:
                # Reconstruct the line
                new_line = prefix + ", ".join(kept_imports) + comment + "\n"
                new_lines.append(new_line)
                continue

        # 2. Handle "import X"
        import_match = re.match(r'^import\s+([\w\.]+)', stripped)
        if import_match:
            module = import_match.group(1)
            if module in unused_symbols:
                continue
        
        # If it wasn't an import line we needed to change, keep it as is
        new_lines.append(line)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    for path, symbols in TASKS.items():
        clean_file(path, symbols)
    print("Cleanup complete.")