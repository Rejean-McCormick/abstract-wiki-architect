# app\adapters\engines\engines\japonic.py
# engines\japonic.py
"""
JAPONIC LANGUAGE ENGINE
-----------------------
A lightweight renderer for Japonic languages (JA, RYU).

Design notes
------------
1. Topic-comment preference:
   The default shape is topic NP + predicate NP + copula.
2. Particle-driven NP composition:
   Topic and genitive markers come from config.
3. No grammatical gender agreement:
   `gender` is accepted for signature compatibility but ignored for morphology.
4. Politeness / register:
   Copula selection is config-driven via `syntax.style` and `verbs.copula`.
5. Script-sensitive spacing:
   Native-script profiles usually suppress spaces; romaji profiles usually keep them.
"""


def render_bio(name, gender, prof_lemma, nat_lemma, config):
    """
    Main Entry Point.

    Args:
        name (str): The subject's name.
        gender (str): Accepted for signature compatibility; ignored for grammar.
        prof_lemma (str): Profession noun.
        nat_lemma (str): Nationality / origin nominal modifier.
        config (dict): The merged language/family configuration card.

    Returns:
        str: The rendered sentence.
    """
    config = config or {}

    name = (name or "").strip()
    profession = (prof_lemma or "").strip()
    nationality = (nat_lemma or "").strip()

    syntax = config.get("syntax", {})
    particles = config.get("particles", {})

    use_spaces = bool(syntax.get("use_spaces", False))
    topic_particle = str(particles.get("topic", "は")).strip() or "は"
    genitive_particle = str(particles.get("genitive", "の")).strip() or "の"
    copula = _select_copula(config)

    predicate = _build_predicate(
        profession=profession,
        nationality=nationality,
        genitive_particle=genitive_particle,
        use_spaces=use_spaces,
    )
    topic_np = _attach_particle(name, topic_particle, use_spaces=use_spaces)

    # Preferred modern template: use `{predicate}` or `{topic_np}`.
    # Legacy support remains for `{topic}`, `{modifier}`, `{profession}`, `{nationality}`.
    structure = config.get(
        "structure",
        "{topic_np} {predicate} {copula}",
    )

    sentence = structure
    sentence = sentence.replace("{name}", name)
    sentence = sentence.replace("{subject}", name)
    sentence = sentence.replace("{topic}", topic_particle)
    sentence = sentence.replace("{topic_np}", topic_np)
    sentence = sentence.replace("{nationality}", nationality)
    sentence = sentence.replace("{modifier}", genitive_particle)
    sentence = sentence.replace("{profession}", profession)
    sentence = sentence.replace("{predicate}", predicate)
    sentence = sentence.replace("{predicate_np}", predicate)
    sentence = sentence.replace("{copula}", copula)
    sentence = sentence.replace("{is_verb}", copula)  # legacy placeholder

    sentence = _normalize_spacing(sentence, use_spaces=use_spaces)
    sentence = _ensure_punctuation(
        sentence,
        punctuation=str(syntax.get("punctuation", "。")).strip() or "。",
    )

    return sentence


def _select_copula(config):
    syntax = config.get("syntax", {})
    verbs = config.get("verbs", {})
    copula_cfg = verbs.get("copula")

    # Very old fallback
    if copula_cfg is None:
        legacy = config.get("copula")
        if isinstance(legacy, str):
            return legacy.strip()
        if isinstance(legacy, dict):
            style = str(syntax.get("style", "plain")).strip() or "plain"
            return (
                legacy.get(style)
                or legacy.get("default")
                or legacy.get("present")
                or ""
            ).strip()
        return ""

    if isinstance(copula_cfg, str):
        return copula_cfg.strip()

    if not isinstance(copula_cfg, dict):
        return ""

    style = str(syntax.get("style", "plain")).strip() or "plain"
    tense = str(
        syntax.get("bio_default_tense", syntax.get("default_tense", "present"))
    ).strip() or "present"

    # Supported shapes:
    # 1) {"plain": "だ", "polite": "です", "default": "だ"}
    # 2) {"present": {"plain": "だ", "polite": "です", "default": "だ"}}
    # 3) {"present": "だ", "default": "だ"}
    if style in copula_cfg:
        selected = copula_cfg.get(style)
        if isinstance(selected, str):
            return selected.strip()

    tense_bucket = copula_cfg.get(tense)
    if isinstance(tense_bucket, str):
        return tense_bucket.strip()
    if isinstance(tense_bucket, dict):
        return (
            tense_bucket.get(style)
            or tense_bucket.get("default")
            or ""
        ).strip()

    return (
        copula_cfg.get("default")
        or copula_cfg.get("present")
        or ""
    ).strip()


def _build_predicate(profession, nationality, genitive_particle, use_spaces):
    if nationality and profession:
        return _join_parts(nationality, genitive_particle, profession, use_spaces=use_spaces)
    if profession:
        return profession
    if nationality:
        return nationality
    return ""


def _attach_particle(text, particle, use_spaces):
    text = (text or "").strip()
    particle = (particle or "").strip()

    if not text:
        return ""
    if not particle:
        return text

    if use_spaces:
        return f"{text} {particle}"
    return f"{text}{particle}"


def _join_parts(*parts, use_spaces):
    cleaned = [str(part).strip() for part in parts if str(part).strip()]
    if not cleaned:
        return ""
    if use_spaces:
        return " ".join(cleaned)
    return "".join(cleaned)


def _normalize_spacing(text, use_spaces):
    text = str(text or "")
    if not use_spaces:
        return text.replace(" ", "").strip()
    return " ".join(text.split())


def _ensure_punctuation(text, punctuation):
    text = (text or "").strip()
    if not text:
        return punctuation if punctuation else ""

    if punctuation and text.endswith(punctuation):
        return text

    if text.endswith((".", "。", "！", "!", "？", "?")):
        return text

    return f"{text}{punctuation}" if punctuation else text