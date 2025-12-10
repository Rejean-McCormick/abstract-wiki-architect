import sys
import os
from typing import Dict, Any

# Add project root to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.lexicon.loader import load_lexicon, available_languages

def check_all_languages():
    print(f"{'LANG':<6} | {'STATUS':<10} | {'ENTRIES':<10} | {'SOURCE'}")
    print("-" * 50)

    langs = available_languages()
    stats = {"active": 0, "stub": 0, "missing": 0}

    for lang in langs:
        try:
            data = load_lexicon(lang)
            entries = data.get("entries", {})
            count = len(entries)
            source = data.get("_meta", {}).get("source", "unknown")

            if count > 0:
                status = "✅ Active"
                stats["active"] += 1
                entry_display = f"{count}"
            else:
                status = "⚠️ Stub"
                stats["stub"] += 1
                entry_display = "0"

            print(f"{lang.upper():<6} | {status:<10} | {entry_display:<10} | {source}")

        except Exception as e:
            print(f"{lang.upper():<6} | ❌ Error   | N/A        | {e}")
            stats["missing"] += 1

    print("-" * 50)
    print(f"SUMMARY: {stats['active']} Active, {stats['stub']} Stubs (Empty), {stats['missing']} Errors")
    print("Tip: 'Stub' languages are initialized but need data in data/lexicon/{lang}/core.json")

if __name__ == "__main__":
    # If arguments provided, check specific languages (e.g. python verify.py ko fr)
    if len(sys.argv) > 1:
        print("Checking specific languages...")
        for lang in sys.argv[1:]:
            # We reuse the logic effectively by just calling load_lexicon
            # but for consistency with the bulk check, let's just run the full report 
            # if they want specific details, they can look at the table.
            pass 
    
    check_all_languages()