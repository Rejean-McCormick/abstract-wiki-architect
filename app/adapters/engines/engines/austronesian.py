# engines\austronesian.py
"""
AUSTRONESIAN LANGUAGE ENGINE
----------------------------
A data-driven renderer for Austronesian languages (ID, MS, TL, MI, HAW).

Key features distinguished from Indo-European:
1. No Grammatical Gender (Native): Most words are neutral.
   *Exception:* Spanish loanwords in Tagalog/Cebuano (Doktor/Doktora).
2. Personal Articles: Specific markers before proper names (e.g., Tagalog 'Si', Maori 'Ko').
3. Focus/Voice: Strict SVO (Malay) vs Predicate-Initial (Tagalog/Maori).
4. Reduplication: Plurals often formed by repeating the word (Orang-orang).
"""


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female'.
        prof_lemma (str): Profession (Base form).
        nat_lemma (str): Nationality (Base form).
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """

    # 1. Normalize Inputs
    gender = gender.lower().strip()
    prof_lemma = prof_lemma.strip()
    nat_lemma = nat_lemma.strip()

    structure = config.get(
        "structure", "{personal_article} {name} {copula} {profession} {nationality}."
    )
    morph_rules = config.get("morphology", {})

    # =================================================================
    # HELPER 1: Gender Inflection (Loanword Handling)
    # =================================================================
    # While native Austronesian words are genderless, Tagalog/Filipino
    # heavily uses Spanish gender rules for professions.
    # e.g., Pilipino (M) -> Pilipina (F), Maestro -> Maestra.

    def inflect_gender(word, target_gender):
        # If language is strictly gender-neutral (e.g. Malay), config will be empty
        if not morph_rules.get("gender_inflection", False):
            return word

        if target_gender == "male":
            return word

        # Check Irregulars
        irregulars = morph_rules.get("irregulars", {})
        if word in irregulars:
            return irregulars[word]

        # Apply Spanish-style Loanword Suffixes
        # config['morphology']['suffixes'] -> [{"ends_with": "o", "replace": "a"}]
        suffixes = morph_rules.get("gender_suffixes", [])

        for rule in suffixes:
            if word.endswith(rule["ends_with"]):
                stem = word[: -len(rule["ends_with"])]
                return stem + rule["replace_with"]

        # Generic Fallback (rarely used in this family, but good for safety)
        return word

    final_prof = inflect_gender(prof_lemma, gender)
    final_nat = inflect_gender(nat_lemma, gender)

    # =================================================================
    # HELPER 2: Personal Articles (The "Si/Ko" Logic)
    # =================================================================
    # Many Austronesian languages require a marker before a Proper Name.
    # Tagalog: "Si Maria"
    # Maori: "Ko Maria"
    # Malay: (None)

    def get_personal_article():
        syntax = config.get("syntax", {})
        article = syntax.get("personal_article", "")

        # Check if article varies by number (Singular/Plural) - Bio is Singular
        if isinstance(article, dict):
            return article.get("singular", "")

        return article

    p_art = get_personal_article()

    # Combine Article + Name
    # We treat this as a unit because some templates might place it differently
    if p_art:
        final_name = f"{p_art} {name}"
    else:
        final_name = name

    # =================================================================
    # HELPER 3: The Copula / Focus Marker
    # =================================================================
    # Malay/Indo: 'adalah' or 'ialah' (Copula)
    # Tagalog: 'ay' (Inversion Marker) - used in SVO order ("Si X ay Y")
    #          If VSO order ("Y si X"), 'ay' is dropped.

    def get_copula():
        verbs = config.get("verbs", {})
        copula = verbs.get("copula", {})
        return copula.get("default", "")

    copula = get_copula()

    # =================================================================
    # HELPER 4: Reduplication (Plural Logic - Optional)
    # =================================================================
    # If the Abstract Content implies "One of many scientists", we might need plural.
    # This prototype assumes Singular, but here is the logic for expansion.

    def reduplicate(word):
        # e.g. "Orang" -> "Orang-orang"
        # Config would define the reduplication strategy (full vs partial)
        mode = morph_rules.get("plural_strategy", "none")
        if mode == "full_reduplication":
            return f"{word}-{word}"
        return word

    # =================================================================
    # 5. ASSEMBLY
    # =================================================================

    # Template: "{personal_article} {name} {copula} {profession} {nationality}."
    # OR Predicate-Initial: "{copula} {profession} {nationality} {personal_article} {name}."

    sentence = structure.replace(
        "{personal_article} {name}", final_name
    )  # Handle grouped
    sentence = sentence.replace("{name}", name)  # Handle split
    sentence = sentence.replace("{personal_article}", p_art)

    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{profession}", final_prof)
    sentence = sentence.replace("{nationality}", final_nat)

    # Clean up double spaces
    sentence = " ".join(sentence.split())

    return sentence
