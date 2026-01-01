import os
import re

# 1. Configuration
# We assume the MD files are inside a 'docs' folder based on the screenshot.
# If they are in the root, change this to '.'
DOCS_DIR = 'docs'

# The specific files identified in the screenshot
TARGET_FILES = [
    "00-SETUP_AND_DEPLOYMENT.md",
    "01-ENGINE_ARCHITECTURE.md",
    "02-BUILD_SYSTEM.md",
    "05-AI_SERVICES.md",
    "06-ADDING_A_LANGUAGE.md",
    "09-AI_CONTEXT_DUMP.md",
    "10-GLOSSARY.md",
    "11-CONTRIBUTING.md",
    "17-TOOLS_AND_TESTS_INVENTORY.md",
    "Abstract_Wiki_Architect_Build_and_Launch_System.md",
    "everythingMatrixUpgrade.md",
    "GF_ARCHITECTURE.md",
    "UPGRADE v2-0 Omni-Upgrade Architecture Specification.md"
]

# Replacement settings
# We use regex to catch both "gf/build_orchestrator.py" and just "build_orchestrator.py"
# and replace them with the new standardized relative path.
OLD_PATTERN = r"(gf/)?build_orchestrator\.py"
NEW_PATH = "builder/orchestrator.py"

def update_documentation():
    print(f"--- Starting Documentation Update ---")
    print(f"Target Directory: {os.path.abspath(DOCS_DIR)}")
    print(f"Replacing pattern '{OLD_PATTERN}' with '{NEW_PATH}'\n")

    files_processed = 0
    files_updated = 0

    for filename in TARGET_FILES:
        file_path = os.path.join(DOCS_DIR, filename)
        
        if not os.path.exists(file_path):
            print(f"[WARNING] File not found, skipping: {filename}")
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Perform the replacement using regex
            # flags=re.IGNORECASE is optional, but files seem consistent with lowercase
            new_content, count = re.subn(OLD_PATTERN, NEW_PATH, content)

            if count > 0:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"[UPDATED]  {filename} ({count} occurrences fixed)")
                files_updated += 1
            else:
                print(f"[SKIPPED]  {filename} (No matches found)")
            
            files_processed += 1

        except Exception as e:
            print(f"[ERROR]    Could not process {filename}: {e}")

    print("-" * 30)
    print(f"Done. Processed {files_processed} files. Updated {files_updated} files.")

if __name__ == "__main__":
    update_documentation()