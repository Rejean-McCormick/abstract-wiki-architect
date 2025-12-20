# app\adapters\engines\engines\agglutinative.py
# engines\agglutinative.py
"""
AGGLUTINATIVE LANGUAGE ENGINE
-----------------------------
A data-driven renderer for Agglutinative languages (TR, HU, FI, ET).

Key features:
1. Vowel Harmony: Suffixes change form based on the root word's vowels.
   - 2-Way (Low Harmony): e.g., Turkish Plural (lar/ler)
   - 4-Way (High Harmony): e.g., Turkish Question (mı/mi/mu/mü)
2. Suffix Chaining: Words are built like LEGOs (Root + Plural + Possessive + Copula).
3. No Grammatical Gender: Most languages in this family ignore the 'gender' input.
"""


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female' (Usually ignored in this family).
        prof_lemma (str): Profession root word.
        nat_lemma (str): Nationality root word.
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """

    # 1. Normalize Inputs
    prof_lemma = prof_lemma.strip()
    nat_lemma = nat_lemma.strip()

    # Load Harmony Rules
    vowels = config.get("phonetics", {}).get("vowels", "aeiou")
    harmony_groups = config.get("phonetics", {}).get("harmony_groups", {})
    structure = config.get("structure", "{name} {nationality} {profession}.")

    # =================================================================
    # HELPER 1: Vowel Analysis
    # =================================================================
    def get_last_vowel(word):
        """Finds the last vowel in a word to trigger harmony."""
        for char in reversed(word):
            if char.lower() in vowels:
                return char.lower()
        # Fallback if no vowels (e.g. acronyms), usually default to back vowel logic
        return config.get("phonetics", {}).get("default_vowel", "a")

    # =================================================================
    # HELPER 2: Suffix Resolver (The Core Logic)
    # =================================================================
    def get_suffix(word, suffix_type):
        """
        Determines the correct suffix variant based on Vowel Harmony.

        Args:
            word (str): The word being attached to.
            suffix_type (str): The abstract name of the suffix (e.g., 'copula', 'plural').
        """
        trigger_vowel = get_last_vowel(word)

        # 1. Find which harmony group the trigger vowel belongs to
        # e.g., 'a' might be in group 'back', 'i' in group 'front'
        active_group = None
        for group_name, group_vowels in harmony_groups.items():
            if trigger_vowel in group_vowels:
                active_group = group_name
                break

        if not active_group:
            return ""

        # 2. Look up the suffix for this type and group
        # config['morphology']['suffixes']['copula']['back'] -> "dır"
        suffix_rules = config.get("morphology", {}).get("suffixes", {})

        if suffix_type in suffix_rules:
            variants = suffix_rules[suffix_type]

            # Check if this suffix uses the specific group (e.g. 'front_rounded')
            # or a broader fallback (e.g. just 'front') if the language simplifies
            if active_group in variants:
                return variants[active_group]

            # Fallback logic for 2-way harmony trying to read 4-way groups
            # (Simplistic mapping for this prototype)
            if "default" in variants:
                return variants["default"]

        return ""

    # =================================================================
    # HELPER 3: Chain Builder
    # =================================================================
    # Agglutinative languages often require a "Copula" (to be) attached
    # to the end of the sentence predicates.

    def apply_predicative_suffixes(root_word):
        """
        Attaches the necessary suffixes to make a noun a predicate.
        e.g., "Student" -> "is a student" (Öğrenci -> Öğrencidir)
        """
        result = root_word

        # 1. Check Buffer Letter (Y-insertion)
        # If word ends in vowel and suffix starts with vowel, add buffer
        # (This is complex, represented simply here)

        # 2. Apply Copula (The "is" suffix)
        # Turkish: -dir/-dır/-dur/-dür
        copula_suffix = get_suffix(result, "copula")

        # Check buffer logic (e.g., Turkish 'y' buffer isn't usually for copula 'd',
        # but might be for other suffixes defined in config)

        return result + copula_suffix

    # Apply logic to the Profession (assuming SOV structure where Prof is last)
    # Note: In Hungarian/Turkish, Nationality usually acts as a raw adjective
    # and doesn't take suffixes when modifying the profession.

    final_nat = nat_lemma  # Adjectives usually don't change in simple Noun Phrases
    final_prof = apply_predicative_suffixes(prof_lemma)

    # =================================================================
    # 4. ASSEMBLY
    # =================================================================

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{nationality}", final_nat)
    sentence = sentence.replace("{profession}", final_prof)

    # Cleanup
    sentence = " ".join(sentence.split())

    return sentence
