# qa_tools/batch_test_generator.py
import csv
import random
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root & logging
# ---------------------------------------------------------------------------


def _find_project_root(start: Path) -> Path:
    """
    Walk upward until we find a directory that looks like the project root.
    Heuristic: contains both 'app' and 'utils' folders.
    """
    for p in [start, *start.parents]:
        if (p / "app").is_dir() and (p / "utils").is_dir():
            return p
    # Fallback: keep prior behavior (works for tools/qa/* layout)
    return start.parents[2] if len(start.parents) >= 3 else start.parent


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# [REFACTOR] Use standardized logger (fallback to stdlib logging)
try:
    from utils.tool_logger import ToolLogger  # type: ignore

    logger = ToolLogger(__file__)
except Exception:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("TestGen")


def _log_info(msg: str) -> None:
    if hasattr(logger, "info"):
        logger.info(msg)
    else:
        print(msg)


def _log_warn(msg: str) -> None:
    if hasattr(logger, "warning"):
        logger.warning(msg)
    else:
        print(f"Warning: {msg}")


# ---------------------------------------------------------------------------
# 1. DATASETS
# ---------------------------------------------------------------------------

NAMES = {
    "Male": [
        "Alessandro",
        "Pierre",
        "Juan",
        "João",
        "Mateo",
        "Sigmund",
        "Hans",
        "Dante",
        "Mateusz",
        "Ivan",
    ],
    "Female": [
        "Maria",
        "Sophie",
        "Elena",
        "Ana",
        "Ioana",
        "Frida",
        "Marie",
        "Julia",
        "Sarah",
        "Alda",
    ],
}

# English Abstract Lemma -> Target Language Lemma
VOCAB = {
    "professions": {
        "Physicist": {
            "it": "fisico",
            "es": "físico",
            "fr": "physicien",
            "pt": "físico",
            "ro": "fizician",
            "de": "Physiker",
            "en": "physicist",
            "ru": "физик",
            "hi": "bhautik_vigyani",
        },
        "Chemist": {
            "it": "chimico",
            "es": "químico",
            "fr": "chimiste",
            "pt": "químico",
            "ro": "chimist",
            "de": "Chemiker",
            "en": "chemist",
            "ru": "химик",
            "hi": "rasayan_shastri",
        },
        "Writer": {
            "it": "scrittore",
            "es": "escritor",
            "fr": "écrivain",
            "pt": "escritor",
            "ro": "scriitor",
            "de": "Schriftsteller",
            "en": "writer",
            "ru": "писатель",
            "hi": "lekhak",
        },
        "Doctor": {
            "it": "medico",
            "es": "doctor",
            "fr": "docteur",
            "pt": "doutor",
            "ro": "doctor",
            "de": "Arzt",
            "en": "doctor",
            "ru": "доктор",
            "hi": "tabib",
        },
        "Teacher": {
            "it": "insegnante",
            "es": "profesor",
            "fr": "enseignant",
            "pt": "professor",
            "ro": "profesor",
            "de": "Lehrer",
            "en": "teacher",
            "ru": "учитель",
            "hi": "adhyapak",
        },
        "Politician": {
            "it": "politico",
            "es": "político",
            "fr": "politicien",
            "pt": "político",
            "ro": "politician",
            "de": "Politiker",
            "en": "politician",
            "ru": "политик",
            "hi": "neta",
        },
    },
    "nationalities": {
        "Italian": {
            "it": "italiano",
            "es": "italiano",
            "fr": "italien",
            "pt": "italiano",
            "ro": "italian",
            "de": "italienisch",
            "en": "italian",
            "ru": "итальянский",
            "hi": "bharatiya",
        },
        "French": {
            "it": "francese",
            "es": "francés",
            "fr": "français",
            "pt": "francês",
            "ro": "francez",
            "de": "französisch",
            "en": "french",
            "ru": "французский",
            "hi": "fransisi",
        },
        "German": {
            "it": "tedesco",
            "es": "alemán",
            "fr": "allemand",
            "pt": "alemão",
            "ro": "german",
            "de": "deutsch",
            "en": "german",
            "ru": "немецкий",
            "hi": "almani",
        },
        "Polish": {
            "it": "polacco",
            "es": "polaco",
            "fr": "polonais",
            "pt": "polonês",
            "ro": "polonez",
            "de": "polnisch",
            "en": "polish",
            "ru": "польский",
            "hi": "polish",
        },
        "American": {
            "it": "americano",
            "es": "americano",
            "fr": "américain",
            "pt": "americano",
            "ro": "american",
            "de": "amerikanisch",
            "en": "american",
            "ru": "американский",
            "hi": "ameriki",
        },
        "Russian": {
            "it": "russo",
            "es": "ruso",
            "fr": "russe",
            "pt": "russo",
            "ro": "rus",
            "de": "russisch",
            "en": "russian",
            "ru": "русский",
            "hi": "russian",
        },
    },
}

CONFIG = {
    # Romance
    "it": {"cop": "è", "art_m": "un", "art_f": "una", "case": "nominative", "is_slavic": False},
    "es": {"cop": "es", "art_m": "un", "art_f": "una", "case": "nominative", "is_slavic": False},
    "fr": {"cop": "est", "art_m": "un", "art_f": "une", "case": "nominative", "is_slavic": False},
    "pt": {"cop": "é", "art_m": "um", "art_f": "uma", "case": "nominative", "is_slavic": False},
    "ro": {"cop": "este", "art_m": "un", "art_f": "o", "case": "nominative", "is_slavic": False},
    # Germanic
    "en": {"cop": "is", "art_m": "a", "art_f": "a", "case": "nominative", "is_slavic": False},
    "de": {"cop": "ist", "art_m": "ein", "art_f": "eine", "case": "nominative", "is_slavic": False},
    "sv": {"cop": "är", "art_m": "en", "art_f": "en", "case": "nominative", "is_slavic": False},
    # Slavic
    "ru": {"cop": "был", "art_m": "", "art_f": "", "case": "instrumental", "is_slavic": True},
    "pl": {"cop": "był", "art_m": "", "art_f": "", "case": "instrumental", "is_slavic": True},
    # Indo-Aryan (Hindi)
    "hi": {"cop": "hain", "art_m": "", "art_f": "", "case": "nominative", "is_slavic": False, "punctuation": "।"},
    # Dravidian (Tamil)
    "ta": {"cop": "", "art_m": "", "art_f": "", "case": "nominative", "is_slavic": False, "punctuation": "."},
}


# ---------------------------------------------------------------------------
# 2. REFERENCE IMPLEMENTATION (Ground Truth Generator)
# ---------------------------------------------------------------------------


def _gender_flags(gender: str) -> tuple[bool, bool]:
    g = (gender or "").strip().lower()
    return (g.startswith("m"), g.startswith("f"))


def feminize(word: str, lang: str) -> str:
    """Generate a feminine form (simplified rules)."""
    # German
    if lang == "de":
        if word.endswith("er") and word != "Lehrer":
            return word[:-2] + "erin"
        if word == "Lehrer":
            return "Lehrerin"
        if word == "Arzt":
            return "Ärztin"
        if word.endswith("e"):
            return word + "rin"
        return word + "in"

    # Slavic (very rough)
    if lang in ("ru", "pl"):
        if word.endswith("тель"):
            return word[:-4] + "тельница"
        if word == "писатель":
            return "писательница"
        if word == "учитель":
            return "учительница"
        if word == "химик":
            return "химичка"
        if word == "доктор":
            return "докторша"
        if word == "физик":
            return "физичка"
        if word.endswith("ик"):
            return word + "иня"

    # Hindi (rough transliteration-ish)
    if lang == "hi":
        if word.endswith("ak"):
            return word[:-2] + "ika"
        if word.endswith("i") and word != "neta":
            return word + "n"
        if word == "neta":
            return "netri"
        if word == "adhyapak":
            return "adhyapika"

    # Romance
    if lang in ("fr", "it", "es", "pt", "ro"):
        if word.endswith("o"):
            return word[:-1] + "a"
        if word == "actor":
            return "actriz"
        if word == "poeta":
            return "poetisa"
        if word.endswith("ol"):
            return word + "a"
        if word.endswith("ês"):
            return word[:-2] + "esa"
        if word.endswith("ain"):
            return word + "e"
        if word.endswith("és"):
            return word + "a"
        if word.endswith(("or", "er", "al")):
            return word + "a"

    return word


def inflect_case_and_adjective(word: str, gender: str, case: str, lang: str) -> str:
    """Apply simplified adjective/case endings."""
    is_male, is_female = _gender_flags(gender)

    # German adjective inflection (very simplified)
    if lang == "de" and case == "nominative":
        if is_male:
            return word + "er"
        if is_female:
            return word + "e"
        return word + "es"

    # Russian instrumental (very simplified)
    if lang == "ru" and case == "instrumental":
        if is_female:
            if word.endswith(("а", "я")):
                return word[:-1] + "ой"
            if word.endswith(("ий", "ый")):
                return word[:-2] + "ой"
            if word.endswith("й"):
                return word[:-1] + "ей"
            return word + "ью"
        if is_male:
            if word.endswith("ик"):
                return word + "ом"
            if word.endswith("ь"):
                return word[:-1] + "ем"
            if word.endswith(("а", "о")):
                return word + "м"
            return word + "ом"

    return word


def _select_copula(cfg: dict, lang: str, gender: str) -> str:
    """Handle a couple of gendered copula cases."""
    _, is_female = _gender_flags(gender)
    if lang == "ru":
        return "была" if is_female else "был"
    if lang == "pl":
        return "była" if is_female else "był"
    return cfg.get("cop", "")


def _needs_an(word: str) -> bool:
    w = (word or "").strip().lower()
    return bool(w) and w[0] in "aeiou"


def generate_sentence(name: str, gender: str, prof: str, nat: str, lang: str) -> str:
    cfg = CONFIG[lang]
    is_slavic = bool(cfg.get("is_slavic", False))

    # Only feminize for female
    _, is_female = _gender_flags(gender)
    prof_base = feminize(prof, lang) if is_female else prof
    nat_base = feminize(nat, lang) if is_female else nat

    target_case = cfg.get("case", "nominative")

    if is_slavic:
        final_prof = inflect_case_and_adjective(prof_base, gender, target_case, lang)
        final_nat = inflect_case_and_adjective(nat_base, gender, target_case, lang)
    else:
        final_nat = inflect_case_and_adjective(nat_base, gender, target_case, lang)
        final_prof = prof_base

    cop = _select_copula(cfg, lang, gender)

    # Articles for some languages
    if lang in ("it", "es", "fr", "pt", "ro", "en", "de", "sv"):
        article = cfg["art_f"] if is_female else cfg["art_m"]

        # English a/an on the word after the article (nationality here)
        if lang == "en" and _needs_an(final_nat):
            article = "an"

        # Italian elision / "uno" is crude; apply based on the word after article (nationality)
        if lang == "it":
            next_word = final_nat
            if next_word.startswith(("a", "e", "i", "o", "u")):
                # un'italiana ...
                article = "un'" if not is_female else "un'"
                np = f"{article}{next_word} {final_prof}".strip()
                sentence = f"{name} {cop} {np}".strip()
            elif next_word.startswith("s") and len(next_word) > 1 and next_word[1] not in "aeiou":
                # uno studente... (very rough)
                article = "uno" if not is_female else "una"
                sentence = f"{name} {cop} {article} {final_nat} {final_prof}".strip()
            elif next_word.startswith(("z", "gn")):
                article = "uno" if not is_female else "una"
                sentence = f"{name} {cop} {article} {final_nat} {final_prof}".strip()
            else:
                sentence = f"{name} {cop} {article} {final_nat} {final_prof}".strip()
        else:
            sentence = f"{name} {cop} {article} {final_nat} {final_prof}".strip()
    else:
        # No-article languages (simplified order)
        sentence = f"{name} {final_nat} {final_prof} {cop}".strip()

    # Normalize whitespace
    sentence = " ".join(sentence.split())

    # Punctuation
    punctuation = cfg.get("punctuation", ".")
    if not sentence.endswith(punctuation):
        sentence += punctuation
    return sentence


# ---------------------------------------------------------------------------
# 3. GENERATOR LOOP
# ---------------------------------------------------------------------------


def main() -> None:
    if hasattr(logger, "start"):
        logger.start("Batch Test Generator")
    else:
        _log_info("Starting Batch Test Generator")

    # Keep datasets next to this script (works for qa_tools/* or tools/qa/*)
    script_dir = Path(__file__).resolve().parent
    output_dir = script_dir / "generated_datasets"
    output_dir.mkdir(parents=True, exist_ok=True)

    target_langs = ["it", "es", "fr", "pt", "ro", "en", "de", "sv", "ru", "pl", "hi", "ta"]
    num_samples = 50
    generated_count = 0

    for lang in target_langs:
        # Must exist in CONFIG and VOCAB for at least one profession/nationality entry
        if lang not in CONFIG:
            _log_warn(f"Skipping {lang} (Missing CONFIG)")
            continue
        if lang not in VOCAB["professions"].get("Physicist", {}):
            _log_warn(f"Skipping {lang} (No base data in VOCAB)")
            continue

        path = output_dir / f"test_suite_{lang}.csv"
        _log_info(f"Generating {num_samples} samples for {lang.upper()}...")

        rows: list[dict[str, str]] = []

        for i in range(num_samples):
            gender = random.choice(["Male", "Female"])
            name = random.choice(NAMES[gender])

            prof_key = random.choice(list(VOCAB["professions"].keys()))
            nat_key = random.choice(list(VOCAB["nationalities"].keys()))

            prof_lemma = VOCAB["professions"][prof_key][lang]
            nat_lemma = VOCAB["nationalities"][nat_key][lang]

            expected = generate_sentence(name, gender, prof_lemma, nat_lemma, lang)

            rows.append(
                {
                    "Test_ID": f"{lang.upper()}_BATCH_{i+1:03d}",
                    "Name": name,
                    "Gender (Male/Female)": gender,
                    f"Profession_Lemma_in_{lang}": prof_lemma,
                    f"Nationality_Lemma_in_{lang}": nat_lemma,
                    "EXPECTED_FULL_SENTENCE": expected,
                }
            )

        if not rows:
            _log_warn(f"Skipping write for {lang} (no rows generated)")
            continue

        headers = list(rows[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

        generated_count += 1

    summary_data = {"datasets_generated": generated_count, "output_dir": str(output_dir)}

    if hasattr(logger, "finish"):
        logger.finish(
            message=f"Done. Generated {generated_count} test suites in {output_dir}",
            details=summary_data,
        )
    else:
        _log_info(f"Done. Generated {generated_count} test suites in {output_dir}")


if __name__ == "__main__":
    main()