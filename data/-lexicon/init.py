"""
data.lexicon
------------

Data-only package containing per-language lexicon JSON files.

This package is not meant to be imported directly for runtime lookups.
Instead, the runtime lexicon subsystem loads JSON files from this
directory via path-based I/O, e.g.:

    from lexicon.loader import load_lexicon

    lexemes = load_lexicon("en")  # reads data/lexicon/en_lexicon.json

Files you will typically find here:

    data/lexicon/en_lexicon.json
    data/lexicon/fr_lexicon.json
    data/lexicon/it_lexicon.json
    data/lexicon/es_lexicon.json
    data/lexicon/...

The presence of this __init__ file simply allows tools that rely on
Python packages (e.g. some IDEs, linters, or test runners) to treat
`data.lexicon` as a valid package if needed.
"""

# This module intentionally exposes no runtime API.
