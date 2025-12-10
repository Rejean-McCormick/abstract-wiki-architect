import os
import json

# The 33 languages currently supported or required by your architecture
TARGET_LANGUAGES = [
    "ar", "bn", "cs", "cy", "da", "de", "en", "es", "fa", "fi", 
    "fr", "he", "hi", "hu", "id", "it", "iu", "ja", "ko", "ml", 
    "nl", "no", "pl", "pt", "ro", "ru", "sv", "sw", "ta", "tr", 
    "zh"
]

# The standard domains defined in your new architecture
DOMAINS = ["core", "people", "science", "geography"]

BASE_DIR = os.path.join("data", "lexicon")

def scaffold_language(lang_code):
    """Creates the folder and 4 standard files for a given language."""
    lang_dir = os.path.join(BASE_DIR, lang_code)
    
    # 1. Create the Directory
    if not os.path.exists(lang_dir):
        os.makedirs(lang_dir)
        print(f"[+] Created directory: {lang_dir}")
    else:
        print(f"[.] Directory exists: {lang_dir}")

    # 2. Create the 4 Domain Files
    for domain in DOMAINS:
        file_path = os.path.join(lang_dir, f"{domain}.json")
        
        if not os.path.exists(file_path):
            # Create a valid empty JSON with metadata
            initial_content = {
                "_meta": {
                    "language": lang_code,
                    "domain": domain,
                    "version": 1
                },
                "entries": {}
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(initial_content, f, indent=2, ensure_ascii=False)
            print(f"    [+] Created: {domain}.json")
        else:
            print(f"    [.] Skipped (exists): {domain}.json")

def main():
    print(f"Initializing Lexicon Structure for {len(TARGET_LANGUAGES)} languages...")
    
    # Ensure base directory exists
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)

    for lang in TARGET_LANGUAGES:
        scaffold_language(lang)

    print("\nDone! To add a new language later, just add it to the list or run this script logic again.")

if __name__ == "__main__":
    main()