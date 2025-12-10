# debug_loader.py
from lexicon import load_lexicon

def test_lang(lang):
    print(f"\n--- Testing {lang.upper()} ---")
    data = load_lexicon(lang)
    entries = data.get("entries", {})
    print(f"Total Entries: {len(entries)}")
    
    # Check for a sample word
    sample = list(entries.keys())[0] if entries else "NONE"
    print(f"Sample: {sample}")

if __name__ == "__main__":
    test_lang("fr")  # French (Romance)
    test_lang("ja")  # Japanese (Altaic)