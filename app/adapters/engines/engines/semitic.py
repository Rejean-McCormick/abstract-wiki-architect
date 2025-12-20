# app\adapters\engines\engines\semitic.py
# engines\semitic.py
"""
SEMITIC LANGUAGE ENGINE
-----------------------
A data-driven renderer for Semitic languages (AR, HE, AM, MT).

Key features distinguished from Indo-European:
1. Nominal Sentences: "X is Y" usually drops the verb "to be" in present tense.
   (e.g., Arabic: "Marie Curie scientist" instead of "Marie Curie is a scientist").
2. Gender Agreement: Strong gender matching for nouns and adjectives.
   (e.g., Hebrew: 'Ish' (Man) -> 'Ishah' (Woman)).
3. Definiteness: Articles are often prefixes (al-, ha-) or suffixes, but
   predicate nouns in biographies are typically Indefinite.
"""


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female'.
        prof_lemma (str): Profession (Masculine Singular).
        nat_lemma (str): Nationality (Masculine Singular).
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """

    # 1. Normalize Inputs
    gender = gender.lower().strip()
    prof_lemma = prof_lemma.strip()
    nat_lemma = nat_lemma.strip()

    morph_rules = config.get("morphology", {})
    structure = config.get("structure", "{name} {profession} {nationality}.")

    # =================================================================
    # HELPER 1: Gender Inflection (Feminization)
    # =================================================================
    # Semitic languages usually add a specific suffix to make a male noun female.
    # Arabic: -a (Ta Marbuta)
    # Hebrew: -a / -it

    def inflect_gender(word, target_gender, is_adjective=False):
        if target_gender == "male":
            return word  # Base form is usually Male

        # Check Irregulars
        irregulars = morph_rules.get("irregulars", {})
        if word in irregulars:
            return irregulars[word]

        # Apply Feminine Suffixes
        # Config example: "feminine_suffixes": [{"ends_with": "i", "replace": "iyya"}, {"default": "a"}]
        suffix_rules = morph_rules.get("gender_inflection", [])

        for rule in suffix_rules:
            # If a specific ending triggers a specific replacement (e.g. Arabic Nisba adjectives)
            if "ends_with" in rule and word.endswith(rule["ends_with"]):
                stem = word[: -len(rule["ends_with"])]
                return stem + rule["replace_with"]

        # Default Feminine Suffix (if no specific ending matched)
        # e.g., Arabic usually adds 'a' (represented as 'h' or 't' depending on transliteration schema)
        default_suffix = morph_rules.get("default_fem_suffix", "")
        return word + default_suffix

    # Apply inflection
    final_prof = inflect_gender(prof_lemma, gender, is_adjective=False)
    final_nat = inflect_gender(nat_lemma, gender, is_adjective=True)

    # =================================================================
    # HELPER 2: Definiteness (The Article)
    # =================================================================
    # In standard biography ("Marie is a scientist"), the predicate is INDEFINITE.
    # However, some structures ("Marie is the scientist who...") require DEFINITE.
    # This helper applies the article prefix/suffix if the config/template demands it.

    def apply_article(word, state="indefinite"):
        if state == "indefinite":
            return word

        article_rules = config.get("articles", {})
        prefix = article_rules.get("definite_prefix", "")
        suffix = article_rules.get("definite_suffix", "")

        # Handle Sun/Moon letters for Arabic (Phonetic assimilation of al-)
        # This is advanced, but we check if config has it.
        sun_letters = config.get("phonetics", {}).get("sun_letters", [])
        if prefix == "al-" and word[0] in sun_letters:
            # In strict transliteration, might change to 'as-', 'ar-', etc.
            # For this prototype, we stick to standard 'al-'.
            pass

        return f"{prefix}{word}{suffix}"

    # For the standard bio template, we usually keep them indefinite.
    # If the template asked for {def_profession}, we would call apply_article.

    # =================================================================
    # HELPER 3: The Copula (To Be)
    # =================================================================
    # Present tense usually has NO verb. Past tense HAS a verb.
    # Config should specify if we are doing Present (default) or Past.

    def get_copula():
        # Default to present tense (Zero Copula) unless specified
        tense = config.get("syntax", {}).get("default_tense", "present")

        if tense == "present":
            # Some languages like Hebrew *can* use a pronoun as a copula (hu/hi)
            # e.g. "Moshe hu moreh" (Moses he [is] teacher).
            return config.get("verbs", {}).get("present_copula", {}).get(gender, "")

        elif tense == "past":
            # Arabic 'kana' / 'kanat'
            return config.get("verbs", {}).get("past_copula", {}).get(gender, "")

        return ""

    copula = get_copula()

    # =================================================================
    # 4. ASSEMBLY
    # =================================================================

    # Semitic Word Order can be VSO or SVO.
    # Nominal sentences are usually Subject - (Copula) - Predicate.

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{profession}", final_prof)
    sentence = sentence.replace("{nationality}", final_nat)

    # Clean up double spaces (common if Copula is empty)
    sentence = " ".join(sentence.split())

    return sentence
