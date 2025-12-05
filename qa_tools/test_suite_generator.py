import csv
import os
import sys
from typing import Dict, Any, Optional

# ---------------------------------------------------------------------------
# Path setup: make sure project root is importable so we can use utils.config_extractor
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Shared loader for the Romance grammar matrix (with multiple fallback paths)
# see: utils/config_extractor.py (DEFAULT_MATRIX_CANDIDATES + load_matrix)
from utils.config_extractor import load_matrix  # noqa: E402


def load_grammar_config(matrix_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load the Romance grammar matrix using the shared helper from utils.config_extractor.

    This reuses the same search logic as the QA runner, trying (in order):

        - data/morphology_configs/romance_grammar_matrix.json
        - data/romance_grammar_matrix.json
        - romance_grammar_matrix.json

    An explicit matrix_path can be passed to override the default search.
    """
    return load_matrix(matrix_path)


def generate_csv_templates(matrix_path: Optional[str] = None) -> None:
    """
    Generates CSV testing templates for each Romance language defined
    in the grammar matrix.

    Each CSV goes to:
        qa_tools/generated_datasets/test_suite_<lang>.csv
    and uses a standard schema consumed by qa/test_runner.py.
    """
    config = load_grammar_config(matrix_path)
    languages = config.get("languages", {})

    if not isinstance(languages, dict) or not languages:
        raise ValueError("Grammar matrix must contain a non-empty 'languages' object.")

    # Output directory (always under project root, even if script is run elsewhere)
    output_dir = os.path.join(PROJECT_ROOT, "qa_tools", "generated_datasets")
    os.makedirs(output_dir, exist_ok=True)

    # Standard Lemmas to test across all languages
    # These are *concepts* in English. For each target language:
    #   1. Translate Profession/Nationality to masculine singular lemmas
    #   2. Fill EXPECTED_FULL_SENTENCE with the fully inflected sentence
    base_test_cases = [
        # (Concept Name, Concept Gender, Profession Concept, Nationality Concept)
        ("Roberto", "Male", "Actor", "Italian"),
        ("Maria", "Female", "Actor", "Italian"),
        ("Enrico", "Male", "Scientist", "Italian"),  # Trap: S+Consonant checks
        ("Sofia", "Female", "Scientist", "Italian"),
        ("Pablo", "Male", "Painter", "Spanish"),
        ("Frida", "Female", "Painter", "Spanish"),
        ("Jean", "Male", "Writer", "French"),
        ("Simone", "Female", "Writer", "French"),
        ("Dante", "Male", "Poet", "Italian"),  # Trap: Irregular (poeta -> poetessa)
        ("Alda", "Female", "Poet", "Italian"),
        ("Sigmund", "Male", "Psychologist", "Austrian"),  # Trap: ps- start
        ("Marie", "Female", "Physicist", "Polish"),
    ]

    lang_codes = list(languages.keys())
    print(f"🏭 QA Factory started. Generating templates for: {', '.join(lang_codes)}")

    for lang_code, lang_cfg in languages.items():
        # Human-friendly language name (fallback to code)
        lang_name = lang_cfg.get("name", lang_code)

        filename = os.path.join(output_dir, f"test_suite_{lang_code}.csv")

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header Columns — must match what qa/test_runner.py expects
            writer.writerow(
                [
                    "Test_ID",
                    "Name",
                    "Gender (Male/Female)",
                    f"Profession_Lemma_in_{lang_name}",
                    f"Nationality_Lemma_in_{lang_name}",
                    "EXPECTED_FULL_SENTENCE",
                ]
            )

            # Write rows
            for i, case in enumerate(base_test_cases, 1):
                test_id = f"{lang_code.upper()}_{i:03d}"
                name, gender, prof_concept, nat_concept = case

                writer.writerow(
                    [
                        test_id,
                        name,
                        gender,
                        f"[{prof_concept}]",  # Placeholder hint
                        f"[{nat_concept}]",  # Placeholder hint
                        "",  # Ground truth to be filled by human/AI
                    ]
                )

        print(f"   ✅ Created {filename}")


if __name__ == "__main__":
    # Normalise CWD to project root so relative paths behave as expected
    os.chdir(PROJECT_ROOT)
    generate_csv_templates()
