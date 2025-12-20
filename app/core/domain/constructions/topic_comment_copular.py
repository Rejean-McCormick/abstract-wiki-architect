# app\core\domain\constructions\topic_comment_copular.py
# constructions\topic_comment_copular.py
"""
constructions/topic_comment_copular.py

A family-agnostic construction module for **topic–comment copular clauses**.

Canonical pattern:

    [TOPIC], (SUBJECT) COPULA PREDICATE

Examples (in different languages/strategies):

    - "As for Marie Curie, she was a Polish physicist."
    - "Marie Curie wa, Pōrando no butsuri-gakusha desu."
    - "Quanto a Marie Curie, ela foi uma física polonesa."

This construction **wraps** a simple equative copular clause (implemented in
`copula_equative_simple`) with a topic phrase.

Responsibilities:

- This module:
    - Decides how to combine TOPIC and COMMENT (equative clause) at clause level.
    - Calls the simple equative construction for the comment part.
- `morph_api`:
    - Builds the topic phrase surface form (with markers, if any).
    - Builds subject, predicate, and copula via the equative construction.
- `lang_profile`:
    - Encodes whether topic–comment is enabled.
    - Encodes ordering of TOPIC vs COMMENT.

--------------------
INTERFACES
--------------------

1. abstract_slots (dict)

Minimal expected shape:

    abstract_slots = {
        "topic": {
            "name": "Marie Curie",
            # optional extra features for topic:
            "features": {...}
        },
        "subject": {
            # subject of the comment clause; may be:
            # - same entity as topic
            # - a pronoun
            # - null (pro-drop) handled by morph_api
            "name": "Marie Curie",   # or "she", etc.
            "person": 3,
            "number": "sg",
            "features": {...}
        },
        "predicate": {
            # free-form structure; passed directly to morph_api:
            "role": "profession+nationality",
            "profession_lemma": "physicist",
            "nationality_lemma": "polish",
            "gender": "female",
            "features": {...}
        },
        "tense": "present",        # or "past", "future", etc.
        "polarity": "affirmative"  # reserved for future use
    }

If `"topic"` is missing, this construction will fall back to using `"subject"`
as the topic as well.

2. lang_profile (dict)

Expected keys relevant to this construction:

    lang_profile = {
        "language_code": "ja",
        "copula": {
            # (used by the inner equative construction)
            "lemma": "be",
            "present_zero": False,
            "past_zero": False,
            "order": "S-COP-PRED"
        },
        "topic": {
            # if False/absent, this construction transparently
            # degrades to a simple equative clause
            "enabled": True,

            # TOPIC–COMMENT or COMMENT–TOPIC (rare but supported)
            # Supported values:
            #   "TOPIC-COMMENT"
            #   "COMMENT-TOPIC"
            "order": "TOPIC-COMMENT",

            # (Optional) hint for punctuation; this module does
            # not enforce punctuation, but makes it available for
            # callers that care.
            # e.g. "comma", "none"
            "separator": "comma",
        }
    }

3. morph_api (object)

This module expects:

    - realize_topic(topic_data: dict, lang_profile: dict) -> str
        *If absent*, we fall back to `realize_subject(topic_data, lang_profile)`

    - realize_subject(subject_data: dict, lang_profile: dict) -> str
    - realize_predicate(predicate_data: dict, lang_profile: dict) -> str
    - realize_copula(tense: str, subject_data: dict, lang_profile: dict) -> str

The last three are used indirectly via `copula_equative_simple.realize`.

--------------------
RETURN VALUE
--------------------

The main entry point is `realize`, which returns:

    {
        "tokens":        [...],
        "text":          "...",
        "topic":         "<topic phrase>",
        "comment":       "<inner equative clause>",
        "comment_parts": {  # full result from copula_equative_simple
            "tokens":   [...],
            "text":     "...",
            "subject":  "...",
            "copula":   "...",
            "predicate":"..."
        }
    }

If topics are disabled in `lang_profile["topic"]["enabled"]`, `realize`
returns the same shape but with `"topic"` empty and `"tokens"` / `"text"`
matching a simple equative clause.
"""

from typing import Any, Dict, List

from . import copula_equative_simple


def _get_topic_config(lang_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safe accessor for the topic configuration.
    """
    topic_cfg = lang_profile.get("topic") or {}
    if not isinstance(topic_cfg, dict):
        return {}
    return topic_cfg


def _get_separator(topic_cfg: Dict[str, Any]) -> str:
    """
    Get a hint for how topic and comment should be separated.

    This construction does not enforce punctuation, but callers can use
    this value (e.g. to insert a comma or particle).
    """
    sep = topic_cfg.get("separator", "comma")
    if not isinstance(sep, str):
        return "comma"
    return sep.lower()


def _realize_topic_phrase(
    topic_data: Dict[str, Any], lang_profile: Dict[str, Any], morph_api: Any
) -> str:
    """
    Realize the topic phrase using morph_api.

    Preferred method:
        morph_api.realize_topic(topic_data, lang_profile)

    Fallback:
        morph_api.realize_subject(topic_data, lang_profile)
    """
    # Try dedicated topic realizer, if present
    if hasattr(morph_api, "realize_topic"):
        topic_str = morph_api.realize_topic(topic_data, lang_profile)
    else:
        # Degrade gracefully: many languages will simply reuse subject form
        topic_str = morph_api.realize_subject(topic_data, lang_profile)

    return topic_str.strip()


def _prepare_comment_slots(abstract_slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip out topic-specific fields and pass everything else to the
    inner copula equative construction.
    """
    comment_slots = dict(abstract_slots)  # shallow copy is enough
    comment_slots.pop("topic", None)
    # The equative construction expects "subject", "predicate", "tense", etc.
    return comment_slots


def realize(
    abstract_slots: Dict[str, Any],
    lang_profile: Dict[str, Any],
    morph_api: Any,
) -> Dict[str, Any]:
    """
    Realize a topic–comment copular clause.

    The comment is always realized as a simple equative clause by
    calling `copula_equative_simple.realize`.

    If `lang_profile["topic"]["enabled"]` is False or absent, this
    construction transparently degrades to a simple equative clause.
    """
    topic_cfg = _get_topic_config(lang_profile)
    topic_enabled = bool(topic_cfg.get("enabled", False))

    # If topics are not enabled, just return a simple equative clause.
    if not topic_enabled:
        comment_slots = _prepare_comment_slots(abstract_slots)
        comment_result = copula_equative_simple.realize(
            comment_slots, lang_profile, morph_api
        )
        return {
            "tokens": comment_result["tokens"],
            "text": comment_result["text"],
            "topic": "",
            "comment": comment_result["text"],
            "comment_parts": comment_result,
        }

    # Topic data; fallback to subject if no explicit topic is given
    topic_data = abstract_slots.get("topic")
    if not topic_data:
        topic_data = abstract_slots.get("subject", {}) or {}

    # 1. Realize the topic phrase
    topic_str = _realize_topic_phrase(topic_data, lang_profile, morph_api)

    # 2. Realize the comment as a simple equative clause
    comment_slots = _prepare_comment_slots(abstract_slots)
    comment_result = copula_equative_simple.realize(
        comment_slots, lang_profile, morph_api
    )
    comment_text = comment_result["text"].strip()

    # 3. Decide order: "TOPIC-COMMENT" vs "COMMENT-TOPIC"
    order = topic_cfg.get("order", "TOPIC-COMMENT")
    if not isinstance(order, str):
        order = "TOPIC-COMMENT"
    order = order.upper().replace(" ", "")

    separator_hint = _get_separator(topic_cfg)
    tokens: List[str] = []

    # We deliberately do not hard-code punctuation here; we simply
    # split topic/comment into distinct tokens. A higher-level layer
    # can turn ["TOPIC", "COMMENT"] into "TOPIC, COMMENT" or
    # "TOPIC wa COMMENT" according to its own rules.
    if order == "COMMENT-TOPIC":
        if comment_text:
            tokens.append(comment_text)
        if topic_str:
            tokens.append(topic_str)
    else:
        # Default: "TOPIC-COMMENT"
        if topic_str:
            tokens.append(topic_str)
        if comment_text:
            tokens.append(comment_text)

    # Strip empties and redundant whitespace
    tokens = [t.strip() for t in tokens if t and t.strip()]
    text = " ".join(tokens)

    return {
        "tokens": tokens,
        "text": text,
        "topic": topic_str,
        "comment": comment_text,
        "comment_parts": comment_result,
        "separator_hint": separator_hint,
    }
