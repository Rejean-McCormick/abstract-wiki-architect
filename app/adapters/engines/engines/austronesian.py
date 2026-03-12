# app\adapters\engines\engines\austronesian.py
# engines\austronesian.py
"""
AUSTRONESIAN LANGUAGE ENGINE
----------------------------
A data-driven renderer for Austronesian languages (ID, MS, TL, MI, HAW).

Key family traits handled here:
1. Mostly no productive grammatical gender in native morphology.
2. Optional personal articles before names (e.g. Tagalog "Si", Māori "Ko").
3. Copula / focus-marker selection driven by config.
4. Flexible predicate order driven by language-card syntax settings.

This module is intentionally config-driven and keeps no hidden state.
"""


def _normalize_gender(gender):
    """Normalize common gender labels to stable values used by configs."""
    if not isinstance(gender, str):
        return ""

    g = gender.strip().lower()
    if g in {"m", "male", "masc", "masculine"}:
        return "male"
    if g in {"f", "female", "fem", "feminine"}:
        return "female"
    return g


def _apply_suffix_rules(word, rules):
    """
    Apply the first matching suffix replacement rule.

    Expected shape:
        [{"ends_with": "o", "replace_with": "a"}, ...]
    """
    if not isinstance(word, str):
        return ""
    if not isinstance(rules, list):
        return word

    sorted_rules = sorted(
        rules,
        key=lambda rule: len(rule.get("ends_with", "")),
        reverse=True,
    )

    for rule in sorted_rules:
        ending = rule.get("ends_with", "")
        replacement = rule.get("replace_with", "")
        if ending and word.endswith(ending):
            return word[: -len(ending)] + replacement

    return word


def _inflect_loanword_gender(word, target_gender, morphology):
    """
    Apply optional Spanish-style loanword feminization where configured.

    Austronesian family defaults to no gender inflection unless the
    language card explicitly enables it.
    """
    if not word:
        return ""

    if target_gender != "female":
        return word

    if not isinstance(morphology, dict):
        return word

    if not morphology.get("gender_inflection", False):
        return word

    irregulars = morphology.get("irregulars", {})
    if isinstance(irregulars, dict) and word in irregulars:
        return irregulars[word]

    return _apply_suffix_rules(word, morphology.get("gender_suffixes", []))


def _select_personal_article(config):
    """
    Resolve the personal article used before proper names.

    Supported shapes:
      syntax.personal_article = "si"
      syntax.personal_article = {"singular": "si", "plural": "sina"}
      particles.personal_article = ...
    """
    syntax = config.get("syntax", {})
    particles = config.get("particles", {})

    article = syntax.get("personal_article", particles.get("personal_article", ""))

    if isinstance(article, dict):
        return article.get("singular") or article.get("default") or ""

    return str(article or "").strip()


def _select_copula(config):
    """
    Resolve the configured copula / focus marker.

    Supported shapes:
      verbs.copula = "ay"
      verbs.copula = {"default": "ay"}
      verbs.copula = {"plain": "ay", "formal": "adalah"}
      verbs.copula = {"subject_initial": "ay", "predicate_initial": ""}
    """
    syntax = config.get("syntax", {})
    verbs = config.get("verbs", {})
    copula_cfg = verbs.get("copula", "")

    if isinstance(copula_cfg, str):
        return copula_cfg.strip()

    if not isinstance(copula_cfg, dict):
        return ""

    style = str(syntax.get("style", "") or syntax.get("bio_style", "")).strip()
    order = str(
        syntax.get("bio_order", "")
        or syntax.get("word_order", "")
        or syntax.get("default_order", "")
    ).strip().lower()

    # Order-specific override first when present.
    if order in {"vso", "predicate_initial", "predicate-first", "predicate_first"}:
        value = copula_cfg.get("predicate_initial")
        if isinstance(value, str):
            return value.strip()

    if order in {"svo", "subject_initial", "subject-first", "subject_first"}:
        value = copula_cfg.get("subject_initial")
        if isinstance(value, str):
            return value.strip()

    # Style-specific override next.
    if style:
        style_value = copula_cfg.get(style)
        if isinstance(style_value, str):
            return style_value.strip()
        if isinstance(style_value, dict):
            return str(style_value.get("default", "")).strip()

    default_value = copula_cfg.get("default", "")
    if isinstance(default_value, str):
        return default_value.strip()

    if isinstance(default_value, dict):
        return str(default_value.get("default", "")).strip()

    return ""


def _maybe_reduplicate(word, config):
    """
    Optional reduplication hook for plural predicate readings.

    This is off by default. To activate, a language card can set:
      syntax.bio_number = "plural"
      morphology.plural_strategy = "full_reduplication"
    """
    if not word:
        return ""

    syntax = config.get("syntax", {})
    morphology = config.get("morphology", {})

    number = str(
        syntax.get("bio_number", "") or syntax.get("predicate_number", "sg")
    ).strip().lower()

    if number not in {"pl", "plural"}:
        return word

    mode = str(morphology.get("plural_strategy", "none")).strip().lower()
    if mode == "full_reduplication":
        return f"{word}-{word}"

    return word


def _build_predicate(profession, nationality, config):
    """
    Build the nominal predicate block.

    Preferred behavior is to assemble one `{predicate}` string and let the
    template place it. Legacy split placeholders remain supported later.
    """
    syntax = config.get("syntax", {})

    order = str(
        syntax.get("predicate_order", "")
        or syntax.get("modifier_order", "")
        or "profession_first"
    ).strip().lower()

    pluralize_target = str(syntax.get("pluralize_target", "profession")).strip().lower()

    final_profession = profession
    final_nationality = nationality

    if pluralize_target in {"profession", "head"}:
        final_profession = _maybe_reduplicate(final_profession, config)
    elif pluralize_target in {"nationality", "modifier"}:
        final_nationality = _maybe_reduplicate(final_nationality, config)
    elif pluralize_target in {"predicate", "all"}:
        combined = " ".join(part for part in [nationality, profession] if part)
        return _maybe_reduplicate(combined, config)

    if order in {
        "nationality_first",
        "modifier_first",
        "modifier_head",
        "adj_noun",
        "adjective_noun",
        "nationality_profession",
    }:
        parts = [final_nationality, final_profession]
    else:
        parts = [final_profession, final_nationality]

    return " ".join(part for part in parts if part).strip()


def _cleanup_text(text):
    """Normalize whitespace and remove spaces before punctuation."""
    sentence = " ".join(str(text or "").split())
    for punct in [".", ",", ";", ":", "!", "?"]:
        sentence = sentence.replace(f" {punct}", punct)
    return sentence.strip()


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point.

    Args:
        name (str): The subject's name.
        gender (str): Natural gender label, used only when config enables
            loanword gender handling.
        prof_lemma (str): Profession lemma / base form.
        nat_lemma (str): Nationality lemma / base form.
        config (dict): The merged JSON configuration card.

    Returns:
        str: The rendered biography sentence.
    """
    # 1. Normalize Inputs
    name = str(name or "").strip()
    gender = _normalize_gender(gender)
    prof_lemma = str(prof_lemma or "").strip()
    nat_lemma = str(nat_lemma or "").strip()

    morphology = config.get("morphology", {})
    syntax = config.get("syntax", {})

    # Prefer a full predicate placeholder, but keep split-tag compatibility.
    structure = config.get("structure", "{subject} {copula} {predicate}.")

    # 2. Optional loanword gender handling
    final_prof = _inflect_loanword_gender(prof_lemma, gender, morphology)

    inflect_nat = bool(
        syntax.get(
            "inflect_nationality_gender",
            morphology.get("inflect_nationality_gender", False),
        )
    )
    final_nat = (
        _inflect_loanword_gender(nat_lemma, gender, morphology)
        if inflect_nat
        else nat_lemma
    )

    # 3. Subject-side markers
    personal_article = _select_personal_article(config)
    subject = f"{personal_article} {name}".strip() if personal_article else name

    # 4. Predicate + copula
    predicate = _build_predicate(final_prof, final_nat, config)
    copula = _select_copula(config)

    # 5. Assembly
    sentence = structure

    # New/preferred placeholders
    sentence = sentence.replace("{subject}", subject)
    sentence = sentence.replace("{predicate}", predicate)

    # Legacy/grouped placeholders
    sentence = sentence.replace("{personal_article} {name}", subject)
    sentence = sentence.replace("{name_with_article}", subject)

    # Legacy/split placeholders
    sentence = sentence.replace("{name}", name)
    sentence = sentence.replace("{personal_article}", personal_article)
    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{is_verb}", copula)  # legacy alias
    sentence = sentence.replace("{profession}", final_prof)
    sentence = sentence.replace("{nationality}", final_nat)

    return _cleanup_text(sentence)