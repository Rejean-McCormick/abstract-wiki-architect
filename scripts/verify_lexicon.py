"""
scripts/verify_lexicon.py
=========================
Checks the status of all language lexicons using the unified loader.
"""
import sys
import os
from typing import Dict, Any

# Add project root to python path so we can import from data.lexicon
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.lexicon.loader import load_lexicon, available_languages

def check_all_languages():
    print(f"{'LANG':<6} | {'STATUS':<10} | {'ENTRIES':<10}")
    print("-" * 40)

    langs = available_languages()
    stats = {"active": 0, "stub": 0, "missing": 0}

    for lang in langs:
        try:
            # FIX: load_lexicon now returns the flattened dictionary directly
            # It does NOT return {"entries": ...} anymore.
            entries = load_lexicon(lang)
            
            # Count keys in the dictionary directly
            count = len(entries)

            if count > 0:
                status = "✅ Active"
                stats["active"] += 1
                entry_display = f"{count}"
            else:
                status = "⚠️ Stub"
                stats["stub"] += 1
                entry_display = "0"

            print(f"{lang.upper():<6} | {status:<10} | {entry_display:<10}")

        except Exception as e:
            print(f"{lang.upper():<6} | ❌ Error   | {e}")
            stats["missing"] += 1

    print("-" * 40)
    print(f"SUMMARY: {stats['active']} Active, {stats['stub']} Stubs (Empty), {stats['missing']} Errors")
    print("Tip: 'Stub' languages are initialized but need data in data/lexicon/{lang}/core.json")

if __name__ == "__main__":
    # If arguments provided, check specific languages (e.g. python verify.py ko fr)
    if len(sys.argv) > 1:
        print("Checking specific languages...")
        # Just running the full check covers everything cleanly
    
    check_all_languages()