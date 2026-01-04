# tests/test_lexicon_loader.py
"""
Basic smoke tests for the lexicon loader.
Verified against v2.0 Schema.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from app.adapters.persistence.lexicon.config import LexiconConfig, set_config
from app.adapters.persistence.lexicon.loader import load_lexicon
from app.adapters.persistence.lexicon.types import Lexicon

@pytest.fixture
def temp_lexicon_dir(tmp_path):
    """
    Creates a temporary lexicon directory with valid v2 schema data
    for multiple languages.
    """
    # 1. French Setup
    fr_dir = tmp_path / "fr"
    fr_dir.mkdir()
    
    fr_data = {
        "meta": {"language": "fr", "schema_version": "2"},
        "physicien": {
            "key": "physicien",
            "lemma": "physicien",
            "pos": "NOUN",
            "sense": "scientist in physics",
            "human": True,
            "gender": "m"
        },
        "polonais": {
            "key": "polonais",
            "lemma": "polonais",
            "pos": "ADJ",
            "sense": "from Poland"
        }
    }
    with open(fr_dir / "core.json", "w", encoding="utf-8") as f:
        json.dump(fr_data, f)

    # 2. Portuguese Setup
    pt_dir = tmp_path / "pt"
    pt_dir.mkdir()
    
    pt_data = {
        "meta": {"language": "pt", "schema_version": "2"},
        "físico": {
            "key": "físico",
            "lemma": "físico",
            "pos": "NOUN",
            "human": True,
            "gender": "m"
        },
        "polonês": {
            "key": "polonês",
            "lemma": "polonês",
            "pos": "ADJ"
        }
    }
    with open(pt_dir / "core.json", "w", encoding="utf-8") as f:
        json.dump(pt_data, f)

    # 3. Russian Setup
    ru_dir = tmp_path / "ru"
    ru_dir.mkdir()
    
    ru_data = {
        "meta": {"language": "ru", "schema_version": "2"},
        "физик": {
            "key": "физик",
            "lemma": "физик",
            "pos": "NOUN",
            "human": True
        },
        "польский": {
            "key": "польский",
            "lemma": "польский",
            "pos": "ADJ"
        }
    }
    with open(ru_dir / "core.json", "w", encoding="utf-8") as f:
        json.dump(ru_data, f)

    return tmp_path


def test_load_lexicon_fr_basic(temp_lexicon_dir) -> None:
    """French lexicon should load and contain key biography lemmas."""
    # Configure loader to use the temp dir
    cfg = LexiconConfig(lexicon_dir=str(temp_lexicon_dir))
    set_config(cfg)

    lex = load_lexicon("fr")
    assert isinstance(lex, Lexicon)
    
    # Check professions map (Lemma)
    assert "physicien" in lex.professions
    phys = lex.professions["physicien"]
    assert phys.pos == "NOUN"
    
    # Check nationalities map (Lemma)
    assert "polonais" in lex.nationalities
    pol = lex.nationalities["polonais"]
    assert pol.pos == "ADJ"


def test_load_lexicon_pt_basic(temp_lexicon_dir) -> None:
    """Portuguese lexicon should load and contain professions and nationalities."""
    cfg = LexiconConfig(lexicon_dir=str(temp_lexicon_dir))
    set_config(cfg)

    lex = load_lexicon("pt")
    assert isinstance(lex, Lexicon)

    assert "físico" in lex.professions
    fis = lex.professions["físico"]
    assert fis.pos == "NOUN"

    assert "polonês" in lex.nationalities
    pol = lex.nationalities["polonês"]
    assert pol.pos == "ADJ"


def test_load_lexicon_ru_basic(temp_lexicon_dir) -> None:
    """Russian lexicon should load and contain professions and nationality adjectives."""
    cfg = LexiconConfig(lexicon_dir=str(temp_lexicon_dir))
    set_config(cfg)

    lex = load_lexicon("ru")
    assert isinstance(lex, Lexicon)

    assert "физик" in lex.professions
    fiz = lex.professions["физик"]
    assert fiz.pos == "NOUN"

    assert "польский" in lex.nationalities
    pol = lex.nationalities["польский"]
    assert pol.pos == "ADJ"


def test_load_lexicon_unknown_language_raises(temp_lexicon_dir) -> None:
    """
    Loading a lexicon for an unknown language should raise a FileNotFoundError.
    """
    cfg = LexiconConfig(lexicon_dir=str(temp_lexicon_dir))
    set_config(cfg)
    
    with pytest.raises(FileNotFoundError):
        load_lexicon("xx")