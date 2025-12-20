# app\core\domain\constructions\topic_comment_eventive.py
# constructions\topic_comment_eventive.py
# constructions/topic_comment_eventive.py

"""
TOPIC–COMMENT EVENTIVE CONSTRUCTION
-----------------------------------

This module implements the TOPIC_COMMENT_EVENTIVE construction, i.e.
sentences of the form:

    "As for X, (eventive clause about X or something related to X)"

Examples:
    "As for Marie Curie, she discovered polonium."
    "As for the experiment, it failed."
    "As for the conference, it took place in Paris."

The construction is *language-family agnostic*. It delegates all morphology
and language-specific details to a MorphologyAPI and an optional language
profile.

Core idea:
    1. Build a TOPIC NP ("Marie Curie", "the experiment").
    2. Optionally attach a topic marker ("wa", "as for", particle, etc.).
    3. Build an EVENT CLAUSE (subject + finite verb [+ optional object]).
    4. Optionally drop the event subject if it is coreferent with the topic
       (common in topic-prominent / pro-drop languages).
    5. Linearize according to language-profile templates.

This module does not know about specific word orders, case systems,
topic particles, etc. Those are expressed as feature bundles and passed
to `morph_api`, and by templates in `lang_profile`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol


__all__ = [
    "MorphologyAPI",
    "TopicCommentEventiveSlots",
    "realize_topic_comment_eventive",
]


class MorphologyAPI(Protocol):
    """
    Minimal protocol that any morphology layer must implement in order to be
    used by this construction.

    A concrete implementation will typically wrap one of your existing
    family engines (Romance, Slavic, Agglutinative, etc.).
    """

    def realize_np(self, role: str, lemma: str, features: Mapping[str, Any]) -> str:
        """
        Realize a noun phrase.

        Args:
            role: Logical role in the clause (e.g. 'topic', 'subject', 'object').
            lemma: Base form / dictionary form of the head.
            features: Arbitrary feature bundle (gender, number, case,
                      definiteness, etc.), interpreted by the engine.

        Returns:
            Surface string for the NP (without surrounding punctuation).
        """
        ...

    def realize_verb(self, lemma: str, features: Mapping[str, Any]) -> str:
        """
        Realize a finite verb form for the main event predicate.

        Args:
            lemma: Base verb lemma, e.g. "discover", "fail", "take place".
            features: Arbitrary feature bundle (tense, aspect, mood, polarity,
                      person, number, transitivity flags, etc.), interpreted by
                      the engine.

        Returns:
            Surface string for the verb (may be a multi-word form).
        """
        ...


@dataclass
class TopicCommentEventiveSlots:
    """
    Input slots for the TOPIC_COMMENT_EVENTIVE construction.

    Required:
        topic_name:
            Surface string for the topic NP (already lexicalized),
            e.g. "Marie Curie", "the experiment", "the conference".
        verb_lemma:
            Lemma for the main event verb, e.g. "discover", "fail",
            "take place".

    Optional:
        event_subject_name:
            Surface string for the subject of the event clause.
            If None, the subject is assumed to be coreferent with the topic
            (and may be realized as a pronoun or dropped, depending on the
            language profile and morphology engine).

        object_lemma:
            Lemma for a direct object (for simple transitive events),
            e.g. "polonium", "the prize". If None, treated as intransitive.

    Feature-like metadata (passed straight through to MorphologyAPI):
        topic_gender, topic_number:
            Features for the topic NP (and often for the event subject).
        subject_gender, subject_number:
            Explicit subject features; if not provided, fall back to
            topic_gender/topic_number.
        tense, aspect, polarity, person:
            Features for the finite verb of the event clause.

    All of these are simply forwarded to the morphology engine; this
    construction does not assign fixed semantics to their values.
    """

    topic_name: str
    verb_lemma: str

    event_subject_name: Optional[str] = None
    object_lemma: Optional[str] = None

    topic_gender: str = "unknown"
    topic_number: str = "sg"

    subject_gender: Optional[str] = None
    subject_number: Optional[str] = None

    tense: str = "past"
    aspect: str = "simple"
    polarity: str = "affirmative"
    person: int = 3

    # Extra arbitrary features that a particular language/engine may want
    extra_topic_features: Dict[str, Any] = field(default_factory=dict)
    extra_subject_features: Dict[str, Any] = field(default_factory=dict)
    extra_object_features: Dict[str, Any] = field(default_factory=dict)
    extra_verb_features: Dict[str, Any] = field(default_factory=dict)


def _normalize_spaces(text: str) -> str:
    """
    Collapse multiple spaces and strip leading/trailing whitespace.
    """
    return " ".join(text.split())


def realize_topic_comment_eventive(
    slots: TopicCommentEventiveSlots,
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: MorphologyAPI,
) -> str:
    """
    Realize a TOPIC_COMMENT_EVENTIVE sentence.

    Args:
        slots:
            Structured inputs for the construction (topic, event, features).
        lang_profile:
            Optional language profile dict. Used for:
                - topic markers
                - whether to drop the event subject if same as topic
                - clause and outer templates

            Recognized keys (all optional):

                topic_marker: str
                    A language-specific marker attached to the topic,
                    e.g. "wa", "については", "as for", etc.
                    Default: "" (no explicit marker).

                drop_event_subject_if_same_as_topic: bool
                    If True and event_subject_name is None or equal to
                    topic_name, the event subject may be omitted from the
                    surface string. Default: False.

                topic_phrase_template: str
                    Template for constructing the topic phrase, with:
                        "{TOPIC}"        -> realized topic NP
                        "{TOPIC_MARKER}" -> topic marker string
                    Default: "{TOPIC} {TOPIC_MARKER}"

                event_clause_template: str
                    Template for the internal event clause, with:
                        "{SUBJ}"  -> realized subject NP (may be empty)
                        "{VERB}"  -> realized finite verb
                        "{OBJ}"   -> realized object NP (may be empty)
                    Default: "{SUBJ} {VERB} {OBJ}"

                topic_eventive_template: str
                    Outer template combining topic phrase and event clause, with:
                        "{TOPIC_PHRASE}" -> result of topic_phrase_template
                        "{CLAUSE}"       -> result of event_clause_template
                    Default: "{TOPIC_PHRASE}, {CLAUSE}"

        morph_api:
            Implementation of MorphologyAPI that knows how to turn feature
            bundles into surface forms for a specific language.

    Returns:
        A fully realized sentence string (no trailing space, but *without*
        final punctuation, which can be added by a higher layer).
    """
    lang_profile = lang_profile or {}

    # ---------------------------------------------------------------------
    # 1. Build TOPIC NP
    # ---------------------------------------------------------------------
    topic_features: Dict[str, Any] = {
        "role": "topic",
        "gender": slots.topic_gender,
        "number": slots.topic_number,
    }
    topic_features.update(slots.extra_topic_features)

    topic_np = morph_api.realize_np(
        role="topic",
        lemma=slots.topic_name,
        features=topic_features,
    )

    # Topic marker (may be empty; could be a bare particle or a phrase)
    topic_marker: str = str(lang_profile.get("topic_marker", "")).strip()

    # Topic phrase template
    topic_phrase_template: str = lang_profile.get(
        "topic_phrase_template",
        "{TOPIC} {TOPIC_MARKER}",
    )

    topic_phrase = topic_phrase_template.format(
        TOPIC=topic_np,
        TOPIC_MARKER=topic_marker,
    )

    # ---------------------------------------------------------------------
    # 2. Build EVENT SUBJECT NP (or possibly drop it)
    # ---------------------------------------------------------------------
    # Decide on subject features, falling back to topic features if needed
    subj_gender = (
        slots.subject_gender if slots.subject_gender is not None else slots.topic_gender
    )
    subj_number = (
        slots.subject_number if slots.subject_number is not None else slots.topic_number
    )

    subject_features: Dict[str, Any] = {
        "role": "subject",
        "gender": subj_gender,
        "number": subj_number,
        "person": slots.person,
    }
    subject_features.update(slots.extra_subject_features)

    # Decide which lemma to use as subject:
    if slots.event_subject_name is None:
        # Semantically same as topic; concrete realization (pronoun vs name vs zero)
        # is left to the morphology engine and language profile.
        subject_lemma = slots.topic_name
        subject_corefers_topic = True
    else:
        subject_lemma = slots.event_subject_name
        subject_corefers_topic = slots.event_subject_name == slots.topic_name

    # Should we drop the event subject?
    drop_subj = bool(lang_profile.get("drop_event_subject_if_same_as_topic", False))
    if drop_subj and subject_corefers_topic:
        subject_np = ""
    else:
        subject_np = morph_api.realize_np(
            role="subject",
            lemma=subject_lemma,
            features=subject_features,
        )

    # ---------------------------------------------------------------------
    # 3. Build OBJECT NP (optional)
    # ---------------------------------------------------------------------
    if slots.object_lemma:
        object_features: Dict[str, Any] = {
            "role": "object",
        }
        object_features.update(slots.extra_object_features)

        object_np = morph_api.realize_np(
            role="object",
            lemma=slots.object_lemma,
            features=object_features,
        )
    else:
        object_np = ""

    # ---------------------------------------------------------------------
    # 4. Build VERB
    # ---------------------------------------------------------------------
    verb_features: Dict[str, Any] = {
        "tense": slots.tense,
        "aspect": slots.aspect,
        "polarity": slots.polarity,
        "person": slots.person,
        "number": subj_number,
        "transitivity": "transitive" if slots.object_lemma else "intransitive",
    }
    verb_features.update(slots.extra_verb_features)

    verb_form = morph_api.realize_verb(
        lemma=slots.verb_lemma,
        features=verb_features,
    )

    # ---------------------------------------------------------------------
    # 5. Build INNER EVENT CLAUSE
    # ---------------------------------------------------------------------
    event_clause_template: str = lang_profile.get(
        "event_clause_template",
        "{SUBJ} {VERB} {OBJ}",
    )

    clause = event_clause_template.format(
        SUBJ=subject_np,
        VERB=verb_form,
        OBJ=object_np,
    )

    # ---------------------------------------------------------------------
    # 6. Combine TOPIC PHRASE + CLAUSE
    # ---------------------------------------------------------------------
    topic_eventive_template: str = lang_profile.get(
        "topic_eventive_template",
        "{TOPIC_PHRASE}, {CLAUSE}",
    )

    sentence = topic_eventive_template.format(
        TOPIC_PHRASE=topic_phrase,
        CLAUSE=clause,
    )

    return _normalize_spaces(sentence)