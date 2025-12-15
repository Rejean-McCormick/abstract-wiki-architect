# engines\dravidian.py
"""
DRAVIDIAN LANGUAGE ENGINE
-------------------------
A data-driven renderer for Dravidian languages (TA, ML, TE, KN).

Key features distinguished from Indo-European:
1. Agglutinative + Inflectional: Suffixes are added, but stems often change (Sandhi).
2. Rational vs. Irrational: Gender usually applies only to "Rational" (Human) nouns.
   (Biographies imply Rational subjects).
3. Pronominal Suffixes: The verb "to be" is often realized as a suffix attached
   to the predicate noun (Profession), agreeing with the subject's gender/person.
4. Zero Copula: Common in Malayalam and informal Tamil.
"""


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female'.
        prof_lemma (str): Profession (Base/Masculine Singular).
        nat_lemma (str): Nationality (Base/Masculine Singular).
        config (dict): The JSON configuration card.

    Returns:
        str: The fully inflected sentence.
    """

    # 1. Normalize Inputs
    gender = gender.lower().strip()
    prof_lemma = prof_lemma.strip()
    nat_lemma = nat_lemma.strip()

    morph_rules = config.get("morphology", {})
    structure = config.get(
        "structure", "{name} {nationality} {profession}{copula_suffix}."
    )

    # =================================================================
    # HELPER 1: Gender Inflection (Noun Class Switching)
    # =================================================================
    # Dravidian languages often switch the final gender marker.
    # Tamil Example: -an (Male) -> -i (Female) or -aL (Female).
    # Telugu Example: -uDu (Male) -> -uralu (Female).

    def inflect_gender(word, target_gender):
        if target_gender == "male":
            return word

        # Check Irregulars
        irregulars = morph_rules.get("irregulars", {})
        if word in irregulars:
            return irregulars[word]

        # Apply Suffix Replacement Rules
        # config['morphology']['gender_suffixes']
        suffixes = morph_rules.get("gender_suffixes", [])
        # Sort by length descending
        sorted_suffixes = sorted(
            suffixes, key=lambda x: len(x.get("ends_with", "")), reverse=True
        )

        for rule in sorted_suffixes:
            ending = rule.get("ends_with", "")
            replacement = rule.get("replace_with", "")

            if word.endswith(ending):
                base = word[: -len(ending)]
                return base + replacement

        # Generic Fallback (Language specific defaults)
        # e.g. Tamil often adds 'i' for feminization of Sanskrit loans
        default_suffix = morph_rules.get("default_fem_suffix", "")
        if default_suffix:
            return word + default_suffix

        return word

    final_prof = inflect_gender(prof_lemma, gender)
    # Nationalities in Dravidian are often invariant adjectives or behave like nouns.
    # We check config to see if they need inflection.
    if config.get("syntax", {}).get("inflect_adjectives", False):
        final_nat = inflect_gender(nat_lemma, gender)
    else:
        final_nat = nat_lemma

    # =================================================================
    # HELPER 2: Pronominal Suffixes / Copula
    # =================================================================
    # Logic:
    # 1. Check if language uses Zero Copula (Malayalam).
    # 2. Check if language uses Pronominal Suffixes (Tamil/Telugu/Kannada).
    #    This attaches the "be" verb directly to the noun.

    copula_str = ""  # Standalone copula
    suffix_str = ""  # Suffix copula

    syntax = config.get("syntax", {})
    copula_type = syntax.get("copula_type", "zero")  # zero, standalone, suffix

    if copula_type == "standalone":
        # Look up verb table (like Indo-Aryan engine)
        verbs = config.get("verbs", {}).get("copula", {})
        copula_str = verbs.get(gender, verbs.get("default", ""))

    elif copula_type == "suffix":
        # Look up pronominal suffixes
        # e.g. Tamil: Male -> -aan, Female -> -aal
        suffixes = config.get("morphology", {}).get("predicative_suffixes", {})
        raw_suffix = suffixes.get(gender, "")

        if raw_suffix:
            # SANDHI CHECK: Buffer insertion
            # If word ends in vowel and suffix starts with vowel, add buffer (v/y)
            # Simplified logic for prototype:
            vowels = "aeiou"
            if final_prof[-1].lower() in vowels and raw_suffix[0].lower() in vowels:
                buffer_char = config.get("phonetics", {}).get("buffer_char", "v")
                suffix_str = buffer_char + raw_suffix
            else:
                suffix_str = raw_suffix

    # =================================================================
    # 3. ASSEMBLY
    # =================================================================

    # We merge the suffix into the profession if it exists
    # e.g. "Maanavan" + "aan" -> "Maanavanaan"
    if suffix_str:
        final_prof = final_prof + suffix_str

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{nationality}", final_nat)
    sentence = sentence.replace("{profession}", final_prof)
    sentence = sentence.replace("{copula}", copula_str)  # Often empty if suffix used

    # Clean up (replace internal placeholder {copula_suffix} if it was in structure)
    sentence = sentence.replace("{copula_suffix}", "")

    # Standard cleanup
    sentence = " ".join(sentence.split())

    return sentence
