# app\adapters\engines\engines\koreanic.py
# engines\koreanic.py
"""
KOREANIC LANGUAGE ENGINE
------------------------
A data-driven renderer for Koreanic languages (KO).

Key features distinguished from Indo-European:
1. SOV Structure: Subject + Particles + Predicate + Copula.
2. Phonetic Harmony (Batchim): Particles change based on whether the
   preceding character ends in a Consonant (Batchim) or Vowel.
   - Topic: eun (C) / neun (V)
   - Subject: i (C) / ga (V)
   - Copula: ieyo (C) / yeyo (V) (in polite speech)
3. Agglutination: Particles and Copulas attach directly to the noun without spaces.
4. Speech Levels: Distinguishes between Plain (Written/Wiki standard) and Polite.
"""


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female'.
        prof_lemma (str): Profession (Noun form).
        nat_lemma (str): Nationality (Noun form).
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """

    # 1. Normalize Inputs
    prof = prof_lemma.strip()
    nat = nat_lemma.strip()

    syntax = config.get("syntax", {})
    particles = config.get("particles", {})
    verbs = config.get("verbs", {})

    # Structure: "{name}{topic} {nationality} {profession}{copula}."
    structure = config.get(
        "structure", "{name}{topic} {nationality} {profession}{copula}."
    )

    # =================================================================
    # HELPER 1: Batchim Detector (Hangul Phonetics)
    # =================================================================
    # To choose 'eun' vs 'neun', we must know if the last char has a final consonant.
    # We use Unicode math for Hangul Syllables (Range AC00-D7A3).

    def has_batchim(word):
        if not word:
            return False

        last_char = word[-1]
        code = ord(last_char)

        # Check if character is within Hangul Syllables range
        if 0xAC00 <= code <= 0xD7A3:
            # (Code - Base) % 28. If 0, no batchim (ends in vowel).
            final_consonant_index = (code - 0xAC00) % 28
            return final_consonant_index > 0

        # Fallback for non-Hangul (e.g. English names written in Latin script)
        # Naive check for Latin vowels
        if last_char.lower() in "aeiou":
            return False
        return True  # Assume consonant ending for safety

    # =================================================================
    # HELPER 2: Particle Selector
    # =================================================================
    # Selects between Consonant/Vowel variants defined in config.
    # Config format: "topic": {"consonant": "eun", "vowel": "neun"}

    def get_particle(word, particle_type):
        rules = particles.get(particle_type, {})

        # If config provides a simple string (invariant), return it
        if isinstance(rules, str):
            return rules

        if has_batchim(word):
            return rules.get("consonant", "")
        else:
            return rules.get("vowel", "")

    topic_marker = get_particle(name, "topic")

    # =================================================================
    # HELPER 3: The Copula (Ida)
    # =================================================================
    # The copula attaches to the Profession.
    # Forms depend on Speech Level (defined in syntax) and Batchim.

    def get_copula(predicate_word):
        # 1. Determine Speech Level (plain, polite, formal)
        # Wikipedia uses 'plain' (Haera-che). Spoken uses 'polite'.
        level = syntax.get("speech_level", "plain")

        copula_rules = verbs.get("copula", {}).get(level, {})

        # If rules are just a string (invariant suffix like 'da'), return it
        if isinstance(copula_rules, str):
            return copula_rules

        # 2. Check Phonetics of the Predicate (Profession)
        if has_batchim(predicate_word):
            return copula_rules.get("consonant", "")
        else:
            return copula_rules.get("vowel", "")

    copula_suffix = get_copula(prof)

    # =================================================================
    # 4. ASSEMBLY
    # =================================================================

    # Korean spacing rules:
    # - Particles attach to previous word.
    # - Copula attaches to previous word.
    # - Words are separated by spaces.

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{topic}", topic_marker)  # No space before particle
    sentence = sentence.replace("{nationality}", nat)
    sentence = sentence.replace("{profession}", prof)
    sentence = sentence.replace("{copula}", copula_suffix)  # No space before copula

    # Cleanup double spaces (if nationality was missing, etc.)
    sentence = " ".join(sentence.split())

    # Add Punctuation (Korean uses standard period '.')
    punctuation = syntax.get("punctuation", ".")
    if not sentence.endswith(punctuation):
        sentence += punctuation

    return sentence
