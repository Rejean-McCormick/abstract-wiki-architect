# engines\japonic.py
"""
JAPONIC LANGUAGE ENGINE
-----------------------
A data-driven renderer for Japonic languages (JA, RYU).

Key features distinguished from Indo-European:
1. Topic-Comment Structure (SOV): Subject + wa + Predicate + Copula.
2. Particles: 'wa' (Topic), 'no' (Genitive/Modifier), 'ga' (Subject).
3. No Grammatical Gender or Number Agreement.
4. Politeness Levels: Distinguishes between Plain ('da') and Polite ('desu').
5. Orthography: Handling of spacing (or lack thereof) for Kanji/Kana vs Romaji.
"""


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point.

    Args:
        name (str): The subject's name.
        gender (str): 'Male' or 'Female' (Ignored for grammar, used for logic if needed).
        prof_lemma (str): Profession (Noun form).
        nat_lemma (str): Nationality (Noun/No-Adjective form).
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

    # Default structure: "{name} {topic} {nationality} {modifier} {profession} {copula}."
    structure = config.get(
        "structure", "{name} {topic} {nationality} {modifier} {profession} {copula}."
    )

    # =================================================================
    # HELPER 1: Particles (The Glue)
    # =================================================================
    # Topic Marker: 'wa' (orthographically 'ha' in Hiragana, but we use the configured string)
    topic_marker = particles.get("topic", "wa")

    # Modifier Marker: 'no'
    # Used to connect the Nationality (Noun) to the Profession (Noun).
    # e.g., "Amerikajin" (American) + "Isha" (Doctor) -> "Amerikajin no Isha".
    modifier_marker = particles.get("genitive", "no")

    # =================================================================
    # HELPER 2: The Copula (Politeness Strategy)
    # =================================================================
    # Biographies can be written in:
    # - Polite form (Desu/Masu) -> Standard for spoken/polite text.
    # - Plain form (Da/De aru) -> Standard for encyclopedic text (Wikipedia).

    def get_copula():
        # Default to 'plain' (encyclopedic) style if not specified
        style = syntax.get("style", "plain")
        copula_forms = verbs.get("copula", {})

        return copula_forms.get(style, copula_forms.get("default", "da"))

    copula = get_copula()

    # =================================================================
    # HELPER 3: Script & Spacing Logic
    # =================================================================
    # Japanese script (Kana/Kanji) typically uses NO spaces.
    # Romaji (Romanized) uses spaces.
    # We check the config to decide how to join components.

    use_spaces = syntax.get("use_spaces", False)

    # =================================================================
    # 4. ASSEMBLY
    # =================================================================

    # In Japanese, the "Article" concept doesn't exist.
    # The structure typically groups: [Name] [Topic] [Nationality] [Mod] [Profession] [Copula]

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{topic}", topic_marker)
    sentence = sentence.replace("{nationality}", nat)
    sentence = sentence.replace("{modifier}", modifier_marker)
    sentence = sentence.replace("{profession}", prof)
    sentence = sentence.replace("{copula}", copula)

    # Clean up placeholders if they weren't used in the template
    # (e.g., if a template hardcoded the particles)

    if not use_spaces:
        # Remove all spaces for native script
        sentence = sentence.replace(" ", "")
    else:
        # Ensure single spaces for Romaji
        sentence = " ".join(sentence.split())

    # Add Punctuation (Full Stop)
    # Japanese uses '。' (Kuten), Romaji uses '.'
    punctuation = syntax.get("punctuation", "。")
    if not sentence.endswith(punctuation) and not sentence.endswith("."):
        sentence += punctuation

    return sentence
