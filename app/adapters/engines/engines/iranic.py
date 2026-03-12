# app\adapters\engines\engines\iranic.py
# engines\iranic.py
"""
IRANIC LANGUAGE ENGINE
----------------------
A data-driven renderer for Iranic languages (FA, PS, KU, TG).

This module orchestrates sentence generation by:
1. Delegating morphology (Ezafe, gender, indefiniteness) to
   `morphology.iranic.IranicMorphology`.
2. Handling sentence structure and assembly.

Notes
-----
- Prefer `{predicate}` in templates when the nationality is absorbed into the
  Ezafe-linked noun phrase.
- Still support split templates using `{profession}` / `{nationality}` for
  compatibility with older cards.
"""

from morphology.iranic import IranicMorphology


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main entry point for Iranic biography leads.

    Args:
        name (str): The subject's name.
        gender (str): Natural gender hint ('Male' / 'Female' / variants).
        prof_lemma (str): Profession lemma (base form).
        nat_lemma (str): Nationality lemma (base form).
        config (dict): The language configuration card.

    Returns:
        str: The fully assembled sentence.
    """
    # 1. Initialize morphology engine
    morph = IranicMorphology(config)

    # 2. Get predicate components
    # Expected shape:
    #   {
    #     "profession": <gender-adjusted profession>,
    #     "nationality": <gender-adjusted nationality>,
    #     "noun_phrase": <Ezafe-linked combined predicate>,
    #     "copula": <copula form>
    #   }
    parts = morph.render_simple_bio_predicates(prof_lemma, nat_lemma, gender)

    profession = parts.get("profession", "") or ""
    nationality = parts.get("nationality", "") or ""
    predicate = parts.get("noun_phrase", "") or ""
    copula = parts.get("copula", "") or ""

    # 3. Assembly
    #
    # Preferred template:
    #   "{name} {predicate} {copula}."
    #
    # Compatibility:
    # - `{profession}` / `{nationality}` for older cards
    # - `{is_verb}` as a legacy copula placeholder
    structure = config.get("structure", "{name} {predicate} {copula}.")

    sentence = structure.replace("{name}", name)
    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{is_verb}", copula)  # legacy placeholder
    sentence = sentence.replace("{predicate}", predicate)
    sentence = sentence.replace("{profession}", profession)
    sentence = sentence.replace("{nationality}", nationality)

    # 4. Cleanup
    sentence = " ".join(sentence.split())

    # 5. Ensure final punctuation
    punctuation = config.get("syntax", {}).get("punctuation", ".")
    if punctuation and not sentence.endswith(punctuation):
        sentence += punctuation

    return sentence