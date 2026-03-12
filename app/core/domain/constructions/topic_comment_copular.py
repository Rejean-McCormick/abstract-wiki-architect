# app/core/domain/constructions/topic_comment_copular.py
"""
constructions/topic_comment_copular.py

A family-agnostic construction module for topic-comment copular clauses.

Canonical pattern:

    [TOPIC], (SUBJECT) COPULA PREDICATE

Examples:

    - "As for Marie Curie, she was a Polish physicist."
    - "Marie Curie wa, Pōrando no butsuri-gakusha desu."
    - "Quanto a Marie Curie, ela foi uma física polonesa."

This construction wraps a simple equative copular clause
(implemented in ``copula_equative_simple``) with a topic phrase.

Canonical runtime notes
=======================

- Stable construction ID: ``topic_comment_copular``
- This is a wrapper construction.
- The wrapped base construction defaults to ``copula_equative_simple``.
- Canonical slot-map shape:

    {
        "topic": {...},         # optional; falls back to "subject"
        "subject": {...},       # optional but typically present
        "predicate": {...},     # forwarded to inner copular construction
        "tense": "present",     # optional
        "polarity": "affirmative"  # optional
    }

This module is responsible for:
- deciding how TOPIC and COMMENT are combined at clause level,
- realizing the topic phrase,
- delegating the comment clause to the base copular construction.

It does not perform language-specific morphology itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from . import copula_equative_simple


__all__ = [
    "MorphologyAPI",
    "TopicCommentCopularSlots",
    "TopicCommentCopularConstruction",
    "realize",
    "realize_topic_comment_copular",
]


class MorphologyAPI(Protocol):
    """
    Optional protocol for topic realization.

    The inner copular construction is responsible for subject/predicate/copula
    realization. This wrapper only needs a topic surface form.
    """

    def realize_topic(self, topic_data: Mapping[str, Any], lang_profile: Mapping[str, Any]) -> str:
        ...

    def realize_subject(self, subject_data: Mapping[str, Any], lang_profile: Mapping[str, Any]) -> str:
        ...


@dataclass(slots=True)
class TopicCommentCopularSlots:
    """
    Canonical slot bundle for ``topic_comment_copular``.
    """

    topic: dict[str, Any] = field(default_factory=dict)
    subject: dict[str, Any] = field(default_factory=dict)
    predicate: dict[str, Any] = field(default_factory=dict)
    tense: str = "present"
    polarity: str = "affirmative"
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, slots: Mapping[str, Any]) -> "TopicCommentCopularSlots":
        if not isinstance(slots, Mapping):
            raise TypeError("slots must be a mapping")

        topic = _mapping_or_empty(slots.get("topic"))
        subject = _mapping_or_empty(slots.get("subject"))
        predicate = _mapping_or_empty(slots.get("predicate"))

        tense = _as_nonempty_text(slots.get("tense"), default="present")
        polarity = _as_nonempty_text(slots.get("polarity"), default="affirmative")

        known_keys = {"topic", "subject", "predicate", "tense", "polarity"}
        extras = {
            str(key): value
            for key, value in slots.items()
            if str(key) not in known_keys
        }

        return cls(
            topic=topic,
            subject=subject,
            predicate=predicate,
            tense=tense,
            polarity=polarity,
            extras=extras,
        )

    def to_comment_slots(self) -> dict[str, Any]:
        """
        Build the slot map for the wrapped base construction.
        """
        payload: dict[str, Any] = {
            "subject": dict(self.subject),
            "predicate": dict(self.predicate),
            "tense": self.tense,
            "polarity": self.polarity,
        }
        payload.update(self.extras)
        return payload

    def effective_topic(self) -> dict[str, Any]:
        """
        Use the explicit topic if present, otherwise fall back to subject.
        """
        if self.topic:
            return dict(self.topic)
        return dict(self.subject)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("expected a mapping for structured slot content")
    return {str(k): v for k, v in value.items()}


def _as_nonempty_text(value: Any, *, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _get_topic_config(lang_profile: Mapping[str, Any] | None) -> dict[str, Any]:
    topic_cfg = {}
    if isinstance(lang_profile, Mapping):
        raw = lang_profile.get("topic") or {}
        if isinstance(raw, Mapping):
            topic_cfg = {str(k): v for k, v in raw.items()}

    return {
        "enabled": bool(topic_cfg.get("enabled", False)),
        "order": _as_nonempty_text(topic_cfg.get("order"), default="TOPIC-COMMENT").upper().replace(" ", ""),
        "separator": _as_nonempty_text(topic_cfg.get("separator"), default="comma").lower(),
    }


def _realize_topic_phrase(
    topic_data: Mapping[str, Any],
    lang_profile: Mapping[str, Any] | None,
    morph_api: Any,
) -> str:
    """
    Realize the topic phrase using ``morph_api``.

    Preferred method:
        morph_api.realize_topic(topic_data, lang_profile)

    Fallback:
        morph_api.realize_subject(topic_data, lang_profile)
    """
    profile = lang_profile if isinstance(lang_profile, Mapping) else {}

    if hasattr(morph_api, "realize_topic"):
        topic_str = morph_api.realize_topic(topic_data, profile)
    elif hasattr(morph_api, "realize_subject"):
        topic_str = morph_api.realize_subject(topic_data, profile)
    else:
        topic_str = str(topic_data.get("name", "")).strip()

    return str(topic_str or "").strip()


def _coerce_comment_result(value: Any) -> dict[str, Any]:
    """
    Normalize the wrapped construction result to a dict.

    Older implementations may return a dict; this helper preserves that
    shape and supplies sensible defaults if needed.
    """
    if isinstance(value, Mapping):
        return {str(k): v for k, v in value.items()}

    text = str(value or "").strip()
    return {
        "construction_id": "copula_equative_simple",
        "tokens": [text] if text else [],
        "text": text,
    }


class TopicCommentCopularConstruction:
    """
    Stable wrapper construction for topic-comment copular clauses.
    """

    id = "topic_comment_copular"
    base_construction_id = "copula_equative_simple"
    required_slots: tuple[str, ...] = ()
    optional_slots: tuple[str, ...] = ("topic", "subject", "predicate", "tense", "polarity")

    def realize(
        self,
        slots: Mapping[str, Any] | TopicCommentCopularSlots,
        lang_profile: Mapping[str, Any] | None,
        morph_api: Any,
    ) -> dict[str, Any]:
        slot_bundle = (
            slots if isinstance(slots, TopicCommentCopularSlots)
            else TopicCommentCopularSlots.from_mapping(slots)
        )

        profile = lang_profile if isinstance(lang_profile, Mapping) else {}
        topic_cfg = _get_topic_config(profile)

        comment_slots = slot_bundle.to_comment_slots()
        comment_result = _coerce_comment_result(
            copula_equative_simple.realize(comment_slots, profile, morph_api)
        )
        comment_text = str(comment_result.get("text", "") or "").strip()
        comment_tokens = [
            str(token).strip()
            for token in comment_result.get("tokens", [])
            if str(token).strip()
        ]

        topic_enabled = topic_cfg["enabled"]

        if not topic_enabled:
            return {
                "construction_id": self.id,
                "tokens": comment_tokens,
                "text": comment_text,
                "topic": "",
                "comment": comment_text,
                "comment_parts": comment_result,
                "separator_hint": topic_cfg["separator"],
                "metadata": {
                    "wrapper_construction_id": self.id,
                    "base_construction_id": str(
                        comment_result.get("construction_id", self.base_construction_id)
                    ),
                    "topic_enabled": False,
                    "order": topic_cfg["order"],
                },
            }

        topic_data = slot_bundle.effective_topic()
        topic_str = _realize_topic_phrase(topic_data, profile, morph_api)

        order = topic_cfg["order"]
        tokens: list[str] = []

        if order == "COMMENT-TOPIC":
            if comment_text:
                tokens.append(comment_text)
            if topic_str:
                tokens.append(topic_str)
        else:
            if topic_str:
                tokens.append(topic_str)
            if comment_text:
                tokens.append(comment_text)

        tokens = [t.strip() for t in tokens if t and t.strip()]
        text = " ".join(tokens)

        return {
            "construction_id": self.id,
            "tokens": tokens,
            "text": text,
            "topic": topic_str,
            "comment": comment_text,
            "comment_parts": comment_result,
            "separator_hint": topic_cfg["separator"],
            "metadata": {
                "wrapper_construction_id": self.id,
                "base_construction_id": str(
                    comment_result.get("construction_id", self.base_construction_id)
                ),
                "topic_enabled": True,
                "order": order,
            },
        }


def realize(
    abstract_slots: Mapping[str, Any],
    lang_profile: Mapping[str, Any] | None,
    morph_api: Any,
) -> dict[str, Any]:
    """
    Backward-compatible legacy entrypoint.
    """
    return TopicCommentCopularConstruction().realize(
        abstract_slots,
        lang_profile,
        morph_api,
    )


def realize_topic_comment_copular(
    slots: Mapping[str, Any] | TopicCommentCopularSlots,
    lang_profile: Mapping[str, Any] | None,
    morph_api: Any,
) -> dict[str, Any]:
    """
    Explicit named entrypoint for newer callers.
    """
    return TopicCommentCopularConstruction().realize(
        slots,
        lang_profile,
        morph_api,
    )