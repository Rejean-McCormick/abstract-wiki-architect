# qa_tools/batch_test_generator.py
import csv
import os
import random
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root & logging
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# [REFACTOR] Use standardized logger
try:
    from utils.tool_logger import ToolLogger
    logger = ToolLogger(__file__)
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger("TestGen")


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
# This expanded list includes Germanic (DE, EN), Slavic (RU, PL), Indo-Aryan (HI), etc.
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

# Consolidated Config (Copulas/Grammatical Defaults)
CONFIG = {
    # Romance
    "it": {
        "cop": "è",
        "art_m": "un",
        "art_f": "una",
        "case": "nominative",
        "is_slavic": False,
    },
    "es": {
        "cop": "es",
        "art_m": "un",
        "art_f": "una",
        "case": "nominative",
        "is_slavic": False,
    },
    "fr": {
        "cop": "est",
        "art_m": "un",
        "art_f": "une",
        "case": "nominative",
        "is_slavic": False,
    },
    # Germanic
    "en": {
        "cop": "is",
        "art_m": "a",
        "art_f": "a",
        "case": "nominative",
        "is_slavic": False,
    },
    "de": {
        "cop": "ist",
        "art_m": "ein",
        "art_f": "eine",
        "case": "nominative",
        "is_slavic": False,
    },
    "sv": {
        "cop": "är",
        "art_m": "en",
        "art_f": "en",
        "case": "nominative",
        "is_slavic": False,
    },
    # Slavic
    "ru": {
        "cop": "был",
        "art_m": "",
        "art_f": "",
        "case": "instrumental",
        "is_slavic": True,
    },
    "pl": {
        "cop": "był",
        "art_m": "",
        "art_f": "",
        "case": "instrumental",
        "is_slavic": True,
    },
    # Indo-Aryan (Hindi)
    "hi": {
        "cop": "hain",
        "art_m": "",
        "art_f": "",
        "case": "nominative",
        "is_slavic": False,
        "punctuation": "।",
    },
    # Dravidian (Tamil) - Copula suffix is handled by feminize/inflect functions
    "ta": {
        "cop": "",
        "art_m": "",
        "art_f": "",
        "case": "nominative",
        "is_slavic": False,
        "punctuation": ".",
    },
}

# ---------------------------------------------------------------------------
# 2. REFERENCE IMPLEMENTATION (Ground Truth Generator)
# ---------------------------------------------------------------------------


def feminize(word, lang):
    """Generates feminine form for ground truth verification (Simplified)."""
    # Slavic/Germanic Noun Feminization (Professions)
    if lang in ["de"]:
        if word.endswith("er") and word != "Lehrer":
            return word[:-2] + "erin"
        if word == "Lehrer":
            return "Lehrerin"
        if word == "Arzt":
            return "Ärztin"
        if word.endswith("e"):
            return word + "rin"
        return word + "in"  # Generic

    if lang in ["ru", "pl"]:  # Slavic Nouns
        if word.endswith("тель"):
            return word[:-4] + "тельница"  # Russian -tel
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

    # Indo-Aryan Noun Feminization
    if lang in ["hi"]:
        if word.endswith("ak"):
            return word[:-2] + "ika"  # lekhak -> lekhika
        if word.endswith("i") and word != "neta":
            return word + "n"
        if word == "neta":
            return "netri"
        if word == "adhyapak":
            return "adhyapika"

    # Romance Adjective/Noun Feminization
    if lang in ["fr", "it", "es", "pt", "ro"]:
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
        if word.endswith("or"):
            return word + "a"
        if word.endswith("er"):
            return word + "a"
        if word.endswith("al"):
            return word + "a"

    return word


def inflect_case_and_adjective(word, gender, case, lang):
    """Applies case/adjective endings based on simplified rules."""

    # 1. Adjective Inflection (Germanic)
    if lang == "de":
        # Simple German indefinite ending: -er, -e, -es
        if case == "nominative":
            if gender == "male":
                return word + "er"
            if gender == "female":
                return word + "e"
            return word + "es"
        return word  # Simplistic fallback

    # 2. Case Declension (Slavic Instrumental)
    if lang == "ru" and case == "instrumental":
        if gender == "female":
            if word.endswith("а") or word.endswith("я"):
                return word[:-1] + "ой"  # Nouns
            if word.endswith("ий") or word.endswith("ый"):
                return word[:-2] + "ой"  # Adjs
            if word.endswith("й"):
                return word[:-1] + "ей"
            return word + "ью"  # Soft sign nouns
        if gender == "male":
            if word.endswith("ик"):
                return word + "ом"
            if word.endswith("ь"):
                return word[:-1] + "ем"
            if word.endswith("а") or word.endswith("о"):
                return word + "м"
            return word + "ом"

    # Invariant for most others
    return word


def generate_sentence(name, gender, prof, nat, lang):
    cfg = CONFIG[lang]
    is_slavic = cfg.get("is_slavic", False)

    # 1. Inflect Noun (Profession) and Adjective (Nationality) for gender
    real_prof_nom = feminize(prof, lang)
    real_nat_nom = feminize(nat, lang)

    # 2. Inflect Adjective/Noun for Case (If Slavic) or Declension (If Germanic)
    target_case = cfg["case"]

    # Slavic: Case Declension
    if is_slavic:
        final_prof = inflect_case_and_adjective(
            real_prof_nom, gender, target_case, lang
        )
        final_nat = inflect_case_and_adjective(real_nat_nom, gender, target_case, lang)

    # Germanic/Romance: Adjective Inflection only applies to Adjective/Nationality
    else:
        final_nat = inflect_case_and_adjective(real_nat_nom, gender, target_case, lang)
        final_prof = real_prof_nom  # Noun usually remains Nominative/Base

    # 3. Article Selection (Romance/Germanic)
    if lang in ["it", "es", "fr", "pt", "en", "de", "sv"]:
        art_str = cfg["art_f"] if gender == "Female" else cfg["art_m"]
        sep = " "
        # Very simple elision/impure S check for ground truth
        if (
            lang == "it"
            and (final_prof.startswith("s") and final_prof[1] not in "aeiou")
            or final_prof.startswith(("z", "a", "e", "i", "o", "u"))
        ):
            art_str = (
                "uno "
                if gender == "Male" and final_prof.startswith(("s", "z", "gn"))
                else (
                    "un'" if final_prof.startswith(("a", "e", "i", "o", "u")) else "un "
                )
            )
            sep = "" if art_str.endswith("'") else " "
        else:
            # Simple a/an for English
            if lang == "en" and final_nat.lower().startswith("a"):
                art_str = "an"
            sep = " "

        # Noun Phrase: Article + Nationality + Profession
        parts = [name, cfg["cop"], art_str, final_nat, final_prof]

    # Slavic/Indo-Aryan/Dravidian (No Articles)
    else:
        # Indo-Aryan/Dravidian Word Order is usually Adj + Noun
        parts = [name, final_nat, final_prof, cfg["cop"]]
        sep = " "

    # 4. Final Assembly
    sentence = sep.join(p for p in parts if p)
    sentence = sentence.replace("  ", " ").strip()

    # Punctuation
    punctuation = cfg.get("punctuation", ".")
    if not sentence.endswith(punctuation):
        sentence += punctuation

    return sentence


# ---------------------------------------------------------------------------
# 3. GENERATOR LOOP
# ---------------------------------------------------------------------------


def main():
    # [REFACTOR] Standardized Start
    if hasattr(logger, "start"):
        logger.start("Batch Test Generator")
    else:
        logger.info("Starting Batch Test Generator")

    output_dir = os.path.join("qa_tools", "generated_datasets")
    os.makedirs(output_dir, exist_ok=True)

    # List of all languages to test
    target_langs = [
        "it",
        "es",
        "fr",
        "pt",
        "ro",
        "en",
        "de",
        "sv",
        "ru",
        "pl",
        "hi",
        "ta",
    ]
    num_samples = 50
    generated_count = 0

    for lang in target_langs:
        filename = f"test_suite_{lang}.csv"
        path = os.path.join(output_dir, filename)

        # Check if we have data for this language
        if lang not in CONFIG or lang not in VOCAB["professions"].get("Physicist", {}):
            logger.warning(f"Skipping {lang} (No base data in VOCAB/CONFIG)")
            continue

        logger.info(f"Generating {num_samples} samples for {lang.upper()}...")

        rows = []

        for i in range(num_samples):
            # Random choices
            gender = random.choice(["Male", "Female"])
            name = random.choice(NAMES[gender])

            # Pick concepts (keys)
            prof_key = random.choice(list(VOCAB["professions"].keys()))
            nat_key = random.choice(list(VOCAB["nationalities"].keys()))

            # Look up lemmas
            prof_lemma = VOCAB["professions"][prof_key][lang]
            nat_lemma = VOCAB["nationalities"][nat_key][lang]

            # Generate Ground Truth
            expected = generate_sentence(name, gender, prof_lemma, nat_lemma, lang)

            row = {
                "Test_ID": f"{lang.upper()}_BATCH_{i+1:03d}",
                "Name": name,
                "Gender (Male/Female)": gender,
                f"Profession_Lemma_in_{lang}": prof_lemma,
                f"Nationality_Lemma_in_{lang}": nat_lemma,
                "EXPECTED_FULL_SENTENCE": expected,
            }
            rows.append(row)

        # Write CSV
        headers = list(rows[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
            generated_count += 1
    
    # [REFACTOR] Standardized Summary
    summary_data = {
        "datasets_generated": generated_count,
        "output_dir": output_dir
    }
    
    if hasattr(logger, "finish"):
        logger.finish(
            message=f"Done. Generated {generated_count} test suites in {output_dir}",
            details=summary_data
        )
    else:
        logger.info(f"Done. Files generated in {output_dir}")


if __name__ == "__main__":
    main()