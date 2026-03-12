# app/core/domain/constructions/passive_event.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from app.core.domain.constructions.base import SlotSignature, SlotSpec, SlotValueKind


CONSTRUCTION_ID = "passive_event"
TokensLike = Union[str, Sequence[str]]

__all__ = [
    "CONSTRUCTION_ID",
    "SLOT_SIGNATURE",
    "TokensLike",
    "PassiveEventSlots",
    "coerce_passive_event_slots",
    "PassiveEventConstruction",
    "realize_passive_event",
]


SLOT_SIGNATURE = SlotSignature(
    (
        SlotSpec(
            name="patient",
            required=True,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Surface or structured patient phrase.",
        ),
        SlotSpec(
            name="verb",
            required=True,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Verb lemma or structured verb payload.",
        ),
        SlotSpec(
            name="agent",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            description="Optional surface or structured agent phrase.",
        ),
        SlotSpec(
            name="tense",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            default_value="past",
        ),
        SlotSpec(
            name="polarity",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_raw_string_fallback=True,
            default_value="affirmative",
        ),
        SlotSpec(
            name="adverbials",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            allow_sequence=True,
            allow_raw_string_fallback=True,
            default_value=[],
            description="Optional adverbial phrases.",
        ),
        SlotSpec(
            name="patient_features",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            default_value={},
        ),
        SlotSpec(
            name="agent_features",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            default_value={},
        ),
        SlotSpec(
            name="verb_features",
            required=False,
            accepted_kinds=(SlotValueKind.ANY,),
            default_value={},
        ),
    )
)


@dataclass(slots=True)
class PassiveEventSlots:
    """
    Canonical runtime inputs for PASSIVE_EVENT.

    Canonical runtime names:
        - patient
        - verb
        - agent

    Legacy aliases preserved:
        - patient_np
        - verb_lemma
        - agent_np
    """

    patient: TokensLike
    verb: str
    agent: Optional[TokensLike] = None

    tense: str = "past"
    polarity: str = "affirmative"
    adverbials: List[TokensLike] = field(default_factory=list)

    patient_features: Dict[str, Any] = field(default_factory=dict)
    agent_features: Dict[str, Any] = field(default_factory=dict)
    verb_features: Dict[str, Any] = field(default_factory=dict)

    @property
    def patient_np(self) -> TokensLike:
        return self.patient

    @property
    def verb_lemma(self) -> str:
        return self.verb

    @property
    def agent_np(self) -> Optional[TokensLike]:
        return self.agent


def _normalize_tokens(value: TokensLike) -> List[str]:
    """
    Normalize a surface phrase into token strings.
    """
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return []
        return cleaned.split()

    return [str(item).strip() for item in value if str(item).strip()]


def _mapping_or_empty(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        return {}
    return {str(k): v for k, v in value.items()}


def _first_non_empty_text(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def _surface_from_slot_value(value: Any, *, field_name: str) -> TokensLike:
    """
    Accept either a ready surface string / token sequence or a shallow mapping.

    Supported mapping keys:
      - surface
      - text
      - name
      - label
      - lemma
      - tokens
    """
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
        raise ValueError(f"Missing required field: {field_name}")

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, Mapping)):
        tokens = [str(item).strip() for item in value if str(item).strip()]
        if tokens:
            return tokens
        raise ValueError(f"Missing required field: {field_name}")

    if isinstance(value, Mapping):
        if "tokens" in value:
            tokens = _normalize_tokens(value["tokens"])
            if tokens:
                return tokens

        text = _first_non_empty_text(
            value.get("surface"),
            value.get("text"),
            value.get("name"),
            value.get("label"),
            value.get("lemma"),
        )
        if text:
            return text

    raise ValueError(f"Missing required field: {field_name}")


def _required_verb_text(value: Any) -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned

    if isinstance(value, Mapping):
        text = _first_non_empty_text(
            value.get("lemma"),
            value.get("surface"),
            value.get("text"),
            value.get("name"),
            value.get("label"),
        )
        if text:
            return text

    raise ValueError("Missing required field: verb")


def _optional_text(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or default
    return str(value).strip() or default


def _coerce_adverbials(value: Any) -> List[TokensLike]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray)):
        return [str(value)]
    if isinstance(value, Sequence):
        return [item for item in value if item is not None]
    raise TypeError("adverbials must be a string or a sequence of phrases")


def coerce_passive_event_slots(value: PassiveEventSlots | Mapping[str, Any]) -> PassiveEventSlots:
    """
    Accept either the typed dataclass or a canonical slot-map/legacy mapping.

    Supported mapping variants:
      - canonical:
          {"patient": "polonium", "verb": "discover", "agent": "Marie Curie"}
      - structured:
          {"patient": {"text": "polonium"}, "verb": {"lemma": "discover"}}
      - legacy:
          {"patient_np": "polonium", "verb_lemma": "discover", "agent_np": "Marie Curie"}
    """
    if isinstance(value, PassiveEventSlots):
        return value

    if not isinstance(value, Mapping):
        raise TypeError("slots must be PassiveEventSlots or a mapping")

    raw_patient = value.get("patient", value.get("patient_np"))
    raw_verb = value.get("verb", value.get("verb_lemma"))
    raw_agent = value.get("agent", value.get("agent_np"))

    if raw_patient is None:
        raise ValueError("Missing required field: patient")
    if raw_verb is None:
        raise ValueError("Missing required field: verb")

    patient_features = _mapping_or_empty(value.get("patient_features"))
    patient_features.update(_mapping_or_empty(value.get("extra_patient_features")))

    agent_features = _mapping_or_empty(value.get("agent_features"))
    agent_features.update(_mapping_or_empty(value.get("extra_agent_features")))

    verb_features = _mapping_or_empty(value.get("verb_features"))
    verb_features.update(_mapping_or_empty(value.get("extra_verb_features")))

    if isinstance(raw_patient, Mapping):
        patient_features = {
            **_mapping_or_empty(raw_patient.get("features")),
            **patient_features,
        }

    if isinstance(raw_agent, Mapping):
        agent_features = {
            **_mapping_or_empty(raw_agent.get("features")),
            **agent_features,
        }

    if isinstance(raw_verb, Mapping):
        verb_features = {
            **_mapping_or_empty(raw_verb.get("features")),
            **verb_features,
        }

    return PassiveEventSlots(
        patient=_surface_from_slot_value(raw_patient, field_name="patient"),
        verb=_required_verb_text(raw_verb),
        agent=None if raw_agent is None else _surface_from_slot_value(raw_agent, field_name="agent"),
        tense=_optional_text(value.get("tense"), "past"),
        polarity=_optional_text(value.get("polarity"), "affirmative"),
        adverbials=_coerce_adverbials(value.get("adverbials")),
        patient_features=patient_features,
        agent_features=agent_features,
        verb_features=verb_features,
    )


class PassiveEventConstruction:
    """
    Language-agnostic passive event construction.

    Canonical slot names:
      - patient
      - verb
      - agent
      - tense
      - polarity
      - adverbials

    Legacy aliases accepted:
      - patient_np
      - verb_lemma
      - agent_np
    """

    id: str = CONSTRUCTION_ID
    slot_signature: SlotSignature = SLOT_SIGNATURE

    def realize(
        self,
        slots: PassiveEventSlots | Mapping[str, Any],
        lang_profile: Mapping[str, Any],
        morph: Any,
    ) -> Dict[str, Any]:
        """
        Realize a passive clause as a sequence of tokens and a surface string.

        Returns a dict with at least:
        - "tokens": List[str]
        - "text": str
        - "roles": {"patient": [...], "agent": [... or None]}
        - "verb": str
        - "meta": {...}
        """
        normalized = coerce_passive_event_slots(slots)

        patient_tokens = _normalize_tokens(normalized.patient)
        if not patient_tokens:
            raise ValueError("passive_event requires a non-empty patient phrase")

        passive_cfg: Mapping[str, Any] = lang_profile.get("passive", {}) or {}

        agent_marker: str = str(passive_cfg.get("agent_marker", "by") or "")
        agent_position: str = str(passive_cfg.get("agent_position", "postverb") or "postverb")
        subject_position: str = str(passive_cfg.get("subject_position", "preverb") or "preverb")
        allow_agentless: bool = bool(passive_cfg.get("allow_agentless", True))

        verb_form = self._make_verb_form(
            morph=morph,
            lemma=normalized.verb,
            tense=normalized.tense,
            polarity=normalized.polarity,
            extra_features=normalized.verb_features,
        )
        verb_tokens = _normalize_tokens(verb_form)

        agent_tokens: Optional[List[str]] = None
        missing_required_agent = False

        if normalized.agent is not None:
            base_agent = _normalize_tokens(normalized.agent)
            if base_agent:
                agent_tokens = [agent_marker, *base_agent] if agent_marker else base_agent
        elif not allow_agentless:
            missing_required_agent = True

        adverbial_chunks: List[List[str]] = [
            _normalize_tokens(adv)
            for adv in normalized.adverbials
            if _normalize_tokens(adv)
        ]

        tokens: List[str] = []

        if subject_position == "postverb":
            tokens.extend(verb_tokens)
            tokens.extend(patient_tokens)
        else:
            tokens.extend(patient_tokens)
            tokens.extend(verb_tokens)

        if agent_tokens:
            if agent_position == "preverb":
                tokens = agent_tokens + tokens
            elif agent_position == "final":
                pass
            else:
                tokens.extend(agent_tokens)

        for chunk in adverbial_chunks:
            tokens.extend(chunk)

        if agent_tokens and agent_position == "final":
            tokens.extend(agent_tokens)

        tokens = [token for token in tokens if token]
        text = " ".join(tokens)

        return {
            "construction_id": self.id,
            "tokens": tokens,
            "text": text,
            "verb": verb_form,
            "roles": {
                "patient": patient_tokens,
                "agent": agent_tokens,
            },
            "meta": {
                "tense": normalized.tense,
                "polarity": normalized.polarity,
                "subject_role": "patient",
                "agent_included": agent_tokens is not None,
                "agent_required_but_missing": missing_required_agent,
                "slot_contract": tuple(spec.name for spec in self.slot_signature.specs),
            },
        }

    @staticmethod
    def _make_verb_form(
        morph: Any,
        lemma: str,
        *,
        tense: str,
        polarity: str,
        extra_features: Mapping[str, Any],
    ) -> str:
        """
        Ask the morphology layer for a passive verb form if possible.
        Fallback: return the lemma unchanged.
        """
        make_verb = getattr(morph, "make_verb_form", None)
        if callable(make_verb):
            return str(
                make_verb(
                    lemma,
                    voice="passive",
                    tense=tense,
                    polarity=polarity,
                    **dict(extra_features),
                )
            )

        realize_verb = getattr(morph, "realize_verb", None)
        if callable(realize_verb):
            features = {
                "voice": "passive",
                "tense": tense,
                "polarity": polarity,
                **dict(extra_features),
            }
            try:
                return str(realize_verb(lemma=lemma, features=features))
            except TypeError:
                return str(realize_verb(lemma, features))

        return lemma


def realize_passive_event(
    slots: PassiveEventSlots | Mapping[str, Any],
    lang_profile: Mapping[str, Any],
    morph: Any,
) -> Dict[str, Any]:
    """
    Convenience functional interface around PassiveEventConstruction.
    """
    return PassiveEventConstruction().realize(slots, lang_profile, morph)