# app\adapters\persistence\lexicon\cli.py
# lexicon\cli.py
# lexicon/cli.py

from __future__ import annotations

import json
import sys
from typing import Any, Dict

from lexicon.loader import load_lexicon


def main() -> None:
    """
    Simple CLI for inspecting lexica.

    Usage:
        python -m lexicon.cli <lang_code>

    Example:
        python -m lexicon.cli fr
    """
    if len(sys.argv) < 2:
        print("Usage: python -m lexicon.cli <lang_code>")
        sys.exit(1)

    lang = sys.argv[1]
    lemmas: Dict[str, Dict[str, Any]] = load_lexicon(lang)

    print(f"Loaded {len(lemmas)} lemmas for language '{lang}'.")
    print()

    # Show a few sample entries
    for i, (lemma, entry) in enumerate(lemmas.items()):
        if i >= 10:
            break
        print(f"- {lemma!r}:")
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        print()
