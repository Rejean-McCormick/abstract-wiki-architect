# app\adapters\engines\engines\polysynthetic.py
# engines\polysynthetic.py
"""
POLYSYNTHETIC LANGUAGE ENGINE
-----------------------------
A data-driven renderer for Polysynthetic languages (IU, QU, KL).

Key features distinguished from Indo-European:
1. Holophrasis: Entire clauses can be expressed as a single word.
2. Verbalizing Suffixes (The Copula): Nouns are turned into verbs via suffixes.
   (e.g., Inuktitut: 'Ilisaiji' [Teacher] -> 'Ilisaiji-u-juq' [He is a teacher]).
3. Complex Phonological Fusion: Suffixes often delete or assimilate the
   preceding sound (k -> ng, q -> r).
4. Ergativity: Subjects might need specific case marking (though usually
   unmarked Absolutive for copula sentences).
"""


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female'.
        prof_lemma (str): Profession (Root/Base).
        nat_lemma (str): Nationality (Root/Base).
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """

    # 1. Normalize Inputs
    prof_lemma = prof_lemma.strip()
    nat_lemma = nat_lemma.strip()

    morph_rules = config.get("morphology", {})
    phonetics = config.get("phonetics", {})
    structure = config.get("structure", "{name} {predicate}.")

    # =================================================================
    # HELPER 1: Phonological Fusion (Sandhi/Assimilation)
    # =================================================================
    # Polysynthetic suffixes react strongly to the stem's ending.
    # Inuktitut Example:
    #   - Stem ends in vowel -> Suffix 'juq'
    #   - Stem ends in 'k' -> Delete 'k', Suffix 'tuq'
    #   - Stem ends in 'q' -> Delete 'q', Suffix 'ruq'

    def apply_suffix(stem, suffix_data):
        if not suffix_data:
            return stem

        # Get the suffix variant map (e.g., {'vowel': 'juq', 'k': 'tuq', 'q': 'ruq'})
        # or just a simple string if invariant.
        variants = (
            suffix_data.get("variants", {})
            if isinstance(suffix_data, dict)
            else {"default": suffix_data}
        )

        if isinstance(suffix_data, str):
            variants = {"default": suffix_data}

        last_char = stem[-1].lower()
        suffix = variants.get("default", "")

        # Check specific ending rules defined in config
        # config['phonetics']['ending_rules'] might classify 'k' as a 'velar' trigger
        char_type = phonetics.get("char_types", {}).get(last_char, "default")

        if char_type in variants:
            suffix = variants[char_type]
        elif last_char in variants:  # Direct char match
            suffix = variants[last_char]

        # Handle Deletion/Assimilation flags
        # e.g., "delete_last_char": true (Common in Inuktitut for k/q stems)
        deletion_rules = (
            suffix_data.get("deletion", []) if isinstance(suffix_data, dict) else []
        )

        if last_char in deletion_rules or char_type in deletion_rules:
            stem = stem[:-1]

        return stem + suffix

    # =================================================================
    # HELPER 2: The "Verbalizer" (Noun -> Verb conversion)
    # =================================================================
    # Turn "Teacher" into "Be a teacher".
    # Inuktitut: -u- (be)
    # Quechua: -ka- (be), though often dropped in 3rd person present

    def verbalize_noun(noun_root):
        # 1. Get the verbalizing suffix (Copula)
        copula_suffix = morph_rules.get("verbalizers", {}).get("copula", {})

        # 2. Apply it to the noun
        verbalized_stem = apply_suffix(noun_root, copula_suffix)

        # 3. Add Person/Number Marking (3rd Person Singular for Bio)
        # Inuktitut: -juq (3sg)
        person_suffix = morph_rules.get("person_markers", {}).get("3sg", {})

        full_word = apply_suffix(verbalized_stem, person_suffix)

        return full_word

    # =================================================================
    # HELPER 3: Nationality Integration
    # =================================================================
    # Strategy A: Nationality is a separate word modifying the noun.
    # Strategy B: Nationality is incorporated or just juxtaposed.
    # We assume juxtaposition for simplicity unless config says otherwise.

    def build_predicate():
        # Step 1: Verbalize the Profession (The Core Predicate)
        # e.g. "Ilisaiji" -> "Ilisaijiujuq" (He is a teacher)
        main_verb_word = verbalize_noun(prof_lemma)

        # Step 2: Handle Nationality
        # In many such languages, Nationality acts as a modifier noun/adjective BEFORE the head.
        # Quechua: "Piruw mama llaqtayuq" (Peru mother land-possessor)

        # Check if Nationality needs specific suffixes (like 'person from')
        # Inuktitut: -miutaq (inhabitant of)
        origin_suffix = morph_rules.get("derivation", {}).get("origin", {})
        if origin_suffix:
            nat_word = apply_suffix(nat_lemma, origin_suffix)
        else:
            nat_word = nat_lemma

        # Combine
        return f"{nat_word} {main_verb_word}"

    final_predicate = build_predicate()

    # =================================================================
    # 4. ASSEMBLY
    # =================================================================

    # Template usually just "{name} {predicate}."
    # Since the "is" logic is buried inside the predicate word.

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{predicate}", final_predicate)

    # Fallback replacements if structure expects split tags (unlikely for this engine)
    sentence = sentence.replace("{profession}", final_predicate)
    sentence = sentence.replace("{nationality}", "")

    # Clean up double spaces
    sentence = " ".join(sentence.split())

    return sentence
