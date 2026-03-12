# app/core/domain/constructions/topic_comment_eventive.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from .base import ClauseInput, ClauseOutput, Construction


@dataclass(slots=True)
class TopicCommentEventiveSlots:
    """
    Legacy compatibility input model for topic-comment eventive clauses.
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

    extra_topic_features: Dict[str, Any] = field(default_factory=dict)
    extra_subject_features: Dict[str, Any] = field(default_factory=dict)
    extra_object_features: Dict[str, Any] = field(default_factory=dict)
    extra_verb_features: Dict[str, Any] = field(default_factory=dict)


class TopicCommentEventiveConstruction(Construction):
    """
    Planner/runtime-friendly topic-comment wrapper around a simple eventive clause.

    Canonical runtime ID:
        topic_comment_eventive

    ClauseInput.roles:
        - "topic"
        - "subject"   (optional; falls back to topic when omitted)
        - "object"    (optional)

    ClauseInput.features:
        - "verb_lemma" (required)
        - "tense"
        - "aspect"
        - "polarity"
        - "person"
        - "drop_event_subject_if_same_as_topic" (optional override)
    """

    id: str = "topic_comment_eventive"

    def realize_clause(
        self,
        abstract: ClauseInput,
        lang_profile: Dict[str, Any],
        morph: Any,
    ) -> ClauseOutput:
        roles = abstract.roles or {}
        features = abstract.features or {}
        profile = lang_profile or {}

        topic_value = roles.get("topic") or roles.get("subject")
        topic_surface = self._realize_np_or_text(
            topic_value,
            role="topic",
            morph=morph,
            fallback_features={},
        )

        subject_value = roles.get("subject")
        subject_corefers_topic = self._corefers_topic(subject_value, topic_value)
        if subject_value is None:
            subject_corefers_topic = True
            subject_value = topic_value

        drop_subj = bool(
            features.get(
                "drop_event_subject_if_same_as_topic",
                profile.get("drop_event_subject_if_same_as_topic", False),
            )
        )

        if drop_subj and subject_corefers_topic:
            subject_surface = ""
        else:
            subject_surface = self._realize_np_or_text(
                subject_value,
                role="subject",
                morph=morph,
                fallback_features={
                    "person": features.get("person", 3),
                },
            )

        object_surface = self._realize_np_or_text(
            roles.get("object"),
            role="object",
            morph=morph,
            fallback_features={},
        )

        verb_surface = self._realize_verb(
            features=features,
            has_object=bool(object_surface),
            morph=morph,
        )

        topic_marker = str(profile.get("topic_marker", "") or "").strip()

        topic_phrase_template = str(
            profile.get("topic_phrase_template", "{TOPIC} {TOPIC_MARKER}")
        )
        event_clause_template = str(
            profile.get("event_clause_template", "{SUBJ} {VERB} {OBJ}")
        )
        outer_template = profile.get("topic_eventive_template")

        topic_phrase = self._normalize_spaces(
            topic_phrase_template.format(
                TOPIC=topic_surface,
                TOPIC_MARKER=topic_marker,
            )
        )

        clause = self._normalize_spaces(
            event_clause_template.format(
                SUBJ=subject_surface,
                VERB=verb_surface,
                OBJ=object_surface,
            )
        )

        order = str(profile.get("topic_comment_order", "TOPIC-COMMENT") or "").upper()
        separator_hint = str(profile.get("topic_separator_hint", ",") or "")

        if outer_template:
            text = self._normalize_spaces(
                str(outer_template).format(
                    TOPIC_PHRASE=topic_phrase,
                    CLAUSE=clause,
                )
            )
            if order == "COMMENT-TOPIC":
                tokens = [t for t in [clause, topic_phrase] if t]
            else:
                tokens = [t for t in [topic_phrase, clause] if t]
        else:
            text, tokens = self._join_topic_comment(
                topic_phrase=topic_phrase,
                clause=clause,
                order=order,
                separator_hint=separator_hint,
                morph=morph,
            )

        return ClauseOutput(
            tokens=tokens,
            text=text,
            metadata={
                "construction_id": self.id,
                "topic": topic_phrase,
                "comment": clause,
                "comment_parts": {
                    "subject": subject_surface,
                    "verb": verb_surface,
                    "object": object_surface,
                },
                "separator_hint": separator_hint,
                "topic_marker": topic_marker,
                "topic_comment_order": order or "TOPIC-COMMENT",
                "dropped_subject": bool(drop_subj and subject_corefers_topic),
                "subject_corefers_topic": subject_corefers_topic,
                "transitivity": "transitive" if object_surface else "intransitive",
            },
        )

    def realize(
        self,
        slots: TopicCommentEventiveSlots | Mapping[str, Any],
        lang_profile: Optional[Mapping[str, Any]],
        morph_api: Any,
    ) -> str:
        """
        Legacy compatibility shim returning plain text.
        """
        abstract = self._legacy_slots_to_clause_input(slots)
        return self.realize_clause(abstract, dict(lang_profile or {}), morph_api).text

    def _legacy_slots_to_clause_input(
        self,
        slots: TopicCommentEventiveSlots | Mapping[str, Any],
    ) -> ClauseInput:
        if isinstance(slots, TopicCommentEventiveSlots):
            topic_ref: Dict[str, Any] = {
                "name": slots.topic_name,
                "features": {
                    "gender": slots.topic_gender,
                    "number": slots.topic_number,
                    **dict(slots.extra_topic_features),
                },
            }

            if slots.event_subject_name is None:
                subject_ref: Dict[str, Any] = dict(topic_ref)
            else:
                subject_ref = {
                    "name": slots.event_subject_name,
                    "features": {
                        "gender": (
                            slots.subject_gender
                            if slots.subject_gender is not None
                            else slots.topic_gender
                        ),
                        "number": (
                            slots.subject_number
                            if slots.subject_number is not None
                            else slots.topic_number
                        ),
                        "person": slots.person,
                        **dict(slots.extra_subject_features),
                    },
                }

            object_ref: Optional[Dict[str, Any]] = None
            if slots.object_lemma:
                object_ref = {
                    "lemma": slots.object_lemma,
                    "features": dict(slots.extra_object_features),
                }

            return ClauseInput(
                roles={
                    "topic": topic_ref,
                    "subject": subject_ref,
                    "object": object_ref,
                },
                features={
                    "verb_lemma": slots.verb_lemma,
                    "tense": slots.tense,
                    "aspect": slots.aspect,
                    "polarity": slots.polarity,
                    "person": slots.person,
                    **dict(slots.extra_verb_features),
                },
            )

        if isinstance(slots, Mapping):
            raw = dict(slots)
            return ClauseInput(
                roles={
                    "topic": raw.get("topic"),
                    "subject": raw.get("subject"),
                    "object": raw.get("object"),
                },
                features={
                    "verb_lemma": raw.get("verb_lemma") or raw.get("verb"),
                    "tense": raw.get("tense", "past"),
                    "aspect": raw.get("aspect", "simple"),
                    "polarity": raw.get("polarity", "affirmative"),
                    "person": raw.get("person", 3),
                    "drop_event_subject_if_same_as_topic": raw.get(
                        "drop_event_subject_if_same_as_topic"
                    ),
                },
            )

        raise TypeError("slots must be TopicCommentEventiveSlots or a mapping")

    def _join_topic_comment(
        self,
        *,
        topic_phrase: str,
        clause: str,
        order: str,
        separator_hint: str,
        morph: Any,
    ) -> tuple[str, list[str]]:
        if order == "COMMENT-TOPIC":
            parts = [p for p in [clause, topic_phrase] if p]
        else:
            parts = [p for p in [topic_phrase, clause] if p]

        if not parts:
            return "", []

        if len(parts) == 1:
            return parts[0], parts

        if separator_hint:
            text = f"{parts[0]}{separator_hint} {parts[1]}"
        else:
            text = " ".join(parts)

        text = self._normalize_spaces(text)
        if hasattr(morph, "normalize_whitespace"):
            try:
                text = morph.normalize_whitespace(text)
            except Exception:
                pass

        return text, parts

    def _realize_np_or_text(
        self,
        value: Any,
        *,
        role: str,
        morph: Any,
        fallback_features: Mapping[str, Any],
    ) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        if isinstance(value, Mapping):
            payload = dict(value)
            features = {}
            raw_features = payload.get("features")
            if isinstance(raw_features, Mapping):
                features.update(dict(raw_features))
            features.update(dict(fallback_features))

            lemma = self._first_text(
                payload,
                "surface",
                "name",
                "label",
                "lemma",
                "text",
                "surface_hint",
            )

            if hasattr(morph, "realize_np"):
                try:
                    return str(
                        morph.realize_np(
                            sem=payload,
                            role=role,
                            features=features,
                        )
                    ).strip()
                except TypeError:
                    if lemma:
                        try:
                            return str(
                                morph.realize_np(
                                    role=role,
                                    lemma=lemma,
                                    features=features,
                                )
                            ).strip()
                        except TypeError:
                            try:
                                return str(
                                    morph.realize_np(role, lemma, features)
                                ).strip()
                            except Exception:
                                pass
                except Exception:
                    pass

            return lemma or ""

        return str(value).strip()

    def _realize_verb(
        self,
        *,
        features: Mapping[str, Any],
        has_object: bool,
        morph: Any,
    ) -> str:
        verb_lemma = str(features.get("verb_lemma") or "").strip()
        if not verb_lemma:
            return ""

        verb_features: Dict[str, Any] = {
            "tense": features.get("tense", "past"),
            "aspect": features.get("aspect", "simple"),
            "polarity": features.get("polarity", "affirmative"),
            "person": features.get("person", 3),
            "transitivity": "transitive" if has_object else "intransitive",
            "verb_role": "topic_comment_eventive",
        }

        if hasattr(morph, "realize_verb"):
            try:
                return str(
                    morph.realize_verb(lemma=verb_lemma, features=verb_features)
                ).strip()
            except TypeError:
                try:
                    return str(morph.realize_verb(verb_lemma, verb_features)).strip()
                except Exception:
                    pass
            except Exception:
                pass

        return verb_lemma

    def _corefers_topic(self, subject_value: Any, topic_value: Any) -> bool:
        if subject_value is None:
            return True

        subj = self._comparable_surface(subject_value)
        topic = self._comparable_surface(topic_value)
        return bool(subj and topic and subj == topic)

    @staticmethod
    def _comparable_surface(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip().casefold()
        if isinstance(value, Mapping):
            for key in ("surface", "name", "label", "lemma", "text"):
                raw = value.get(key)
                if isinstance(raw, str) and raw.strip():
                    return raw.strip().casefold()
        return str(value).strip().casefold()

    @staticmethod
    def _first_text(mapping: Mapping[str, Any], *keys: str) -> str:
        for key in keys:
            raw = mapping.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""

    @staticmethod
    def _normalize_spaces(text: str) -> str:
        return " ".join((text or "").split()).strip()


def realize_topic_comment_eventive(
    slots: TopicCommentEventiveSlots | Mapping[str, Any],
    lang_profile: Optional[Mapping[str, Any]],
    morph_api: Any,
) -> str:
    """
    Legacy convenience wrapper.
    """
    return TopicCommentEventiveConstruction().realize(slots, lang_profile, morph_api)


__all__ = [
    "TopicCommentEventiveSlots",
    "TopicCommentEventiveConstruction",
    "realize_topic_comment_eventive",
]