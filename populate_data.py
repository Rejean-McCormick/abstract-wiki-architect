import csv
import os

# Data definitions for the concepts
DATA = {
    "it": {
        "Actor": "attore",
        "Italian": "italiano",
        "Scientist": "scienziato",
        "Painter": "pittore",
        "Spanish": "spagnolo",
        "Writer": "scrittore",
        "French": "francese",
        "Poet": "poeta",
        "Psychologist": "psicologo",
        "Austrian": "austriaco",
        "Physicist": "fisico",
        "Polish": "polacco",
        "copula": "è",
        "articles": {"m": "un", "f": "una", "vowel_m": "un", "vowel_f": "un'"},
        "struct": "{name} {cop} {art}{prof} {nat}.",
    },
    "es": {
        "Actor": "actor",
        "Italian": "italiano",
        "Scientist": "científico",
        "Painter": "pintor",
        "Spanish": "español",
        "Writer": "escritor",
        "French": "francés",
        "Poet": "poeta",
        "Psychologist": "psicólogo",
        "Austrian": "austriaco",
        "Physicist": "físico",
        "Polish": "polaco",
        "copula": "es",
        "articles": {"m": "un", "f": "una", "vowel_m": "un", "vowel_f": "una"},
        "struct": "{name} {cop} {art} {prof} {nat}.",
    },
    "fr": {
        "Actor": "acteur",
        "Italian": "italien",
        "Scientist": "scientifique",
        "Painter": "peintre",
        "Spanish": "espagnol",
        "Writer": "écrivain",
        "French": "français",
        "Poet": "poète",
        "Psychologist": "psychologue",
        "Austrian": "autrichien",
        "Physicist": "physicien",
        "Polish": "polonais",
        "copula": "est",
        "articles": {"m": "un", "f": "une", "vowel_m": "un", "vowel_f": "une"},
        "struct": "{name} {cop} {art} {prof} {nat}.",
    },
    "pt": {
        "Actor": "ator",
        "Italian": "italiano",
        "Scientist": "cientista",
        "Painter": "pintor",
        "Spanish": "espanhol",
        "Writer": "escritor",
        "French": "francês",
        "Poet": "poeta",
        "Psychologist": "psicólogo",
        "Austrian": "austríaco",
        "Physicist": "físico",
        "Polish": "polonês",
        "copula": "é",
        "articles": {"m": "um", "f": "uma", "vowel_m": "um", "vowel_f": "uma"},
        "struct": "{name} {cop} {art} {prof} {nat}.",
    },
    "ro": {
        "Actor": "actor",
        "Italian": "italian",
        "Scientist": "om de știință",
        "Painter": "pictor",
        "Spanish": "spaniol",
        "Writer": "scriitor",
        "French": "francez",
        "Poet": "poet",
        "Psychologist": "psiholog",
        "Austrian": "austriac",
        "Physicist": "fizician",
        "Polish": "polonez",
        "copula": "este",
        "articles": {"m": "un", "f": "o", "vowel_m": "un", "vowel_f": "o"},
        "struct": "{name} {cop} {art} {prof} {nat}.",
    },
}


def fem(word, lang):
    """Manual feminization logic for ground truth generation."""
    if lang == "it":
        if word.endswith("o"):
            return word[:-1] + "a"
        if word.endswith("tore"):
            return word[:-4] + "trice"
        if word == "poeta":
            return "poetessa"
        if word == "scienziato":
            return "scienziata"

    if lang == "es":
        # Irregulars matching engine config
        if word == "actor":
            return "actriz"
        if word == "poeta":
            return "poetisa"
        if word == "francés":
            return "francesa"

        if word.endswith("o"):
            return word[:-1] + "a"
        if word.endswith("or"):
            return word + "a"
        if word.endswith("ol"):
            return word + "a"

    if lang == "fr":
        if word == "acteur":
            return "actrice"
        if word == "musicien":
            return "musicienne"
        if word == "italien":
            return "italienne"
        if word == "autrichien":
            return "autrichienne"
        if word == "physicien":
            return "physicienne"
        if word == "polonais":
            return "polonaise"
        if word == "français":
            return "française"
        if word == "espagnol":
            return "espagnole"

    if lang == "pt":
        if word == "ator":
            return "atriz"
        if word.endswith("o"):
            return word[:-1] + "a"
        if word.endswith("ês"):
            return word[:-2] + "esa"
        if word.endswith("ol"):
            return word + "a"  # espanhol -> espanhola
        if word.endswith("or"):
            return word + "a"  # pintor -> pintora

    if lang == "ro":
        if word.endswith("or"):
            return word[:-2] + "oare"
        if word.endswith("an"):
            return word + "ă"
        if word.endswith("ez"):
            return word + "ă"
        if word == "austriac":
            return "austriacă"
        if word == "fizician":
            return "fiziciană"

    return word


def get_italian_article(next_word, gender):
    # Simplified logic for "s-impure" to match engine tests
    is_vowel = next_word[0].lower() in "aeiou"

    if gender == "Female":
        if is_vowel:
            return "un'"
        return "una "

    # Male
    if is_vowel:
        return "un "

    s_impure = (
        next_word.startswith("s") and len(next_word) > 1 and next_word[1] not in "aeiou"
    )
    z_gn_ps = next_word.startswith(("z", "gn", "ps", "pn", "x", "y"))

    if s_impure or z_gn_ps:
        return "uno "

    return "un "


def run():
    base_dir = os.path.join("qa_tools", "generated_datasets")

    for lang, vocab in DATA.items():
        filename = f"test_suite_{lang}.csv"
        filepath = os.path.join(base_dir, filename)

        if not os.path.exists(filepath):
            continue

        print(f"Populating {filename}...")
        updated_rows = []

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

            prof_header = [h for h in fieldnames if "Profession_Lemma" in h][0]
            nat_header = [h for h in fieldnames if "Nationality_Lemma" in h][0]

            for row in reader:
                prof_key = row[prof_header].replace("[", "").replace("]", "")
                nat_key = row[nat_header].replace("[", "").replace("]", "")
                gender = row["Gender (Male/Female)"]
                name = row["Name"]

                prof_lemma = vocab.get(prof_key, prof_key)
                nat_lemma = vocab.get(nat_key, nat_key)

                real_prof = prof_lemma
                real_nat = nat_lemma
                if gender == "Female":
                    real_prof = fem(prof_lemma, lang)
                    real_nat = fem(nat_lemma, lang)

                if lang == "it":
                    art_str = get_italian_article(real_prof, gender)
                    sep = ""
                else:
                    art_str = vocab["articles"]["m"]
                    if gender == "Female":
                        art_str = vocab["articles"]["f"]
                        if lang == "fr" and real_prof[0] in "aeiou":
                            art_str = vocab["articles"]["vowel_f"]
                    elif lang == "fr" and real_prof[0] in "aeiou":
                        art_str = vocab["articles"]["vowel_m"]

                    sep = " "
                    if art_str.endswith("'"):
                        sep = ""

                cop = vocab["copula"]

                if lang == "it":
                    sentence = f"{name} {cop} {art_str}{real_prof} {real_nat}."
                else:
                    sentence = f"{name} {cop} {art_str}{sep}{real_prof} {real_nat}."

                sentence = sentence.replace("  ", " ")

                row[prof_header] = prof_lemma
                row[nat_header] = nat_lemma
                row["EXPECTED_FULL_SENTENCE"] = sentence

                updated_rows.append(row)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)


if __name__ == "__main__":
    run()
