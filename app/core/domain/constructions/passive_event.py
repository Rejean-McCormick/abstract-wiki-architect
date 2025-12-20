# app\core\domain\constructions\passive_event.py
# constructions\passive_event.py
"""
Passive event construction.

This module implements a language-agnostic PASSIVE_EVENT construction, which
encodes propositions of the form:

    PATIENT is V-ed (by AGENT) (ADVERBIALS...)

The construction is responsible for:
- Choosing a linear order for PATIENT, VERB, AGENT-PHRASE, ADVERBIALS
  based on the language profile.
- Building an optional "by"-phrase (or equivalent) for the agent.

It is deliberately *not* responsible for internal verb morphology; it expects
a morphology object that can optionally provide a `make_verb_form(...)`
method. If that method is missing, the raw verb lemma is used as-is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union


TokensLike = Union[str, Sequence[str]]


def _normalize_tokens(value: TokensLike) -> List[str]:
    """
    Normalize various NP / phrase inputs into a list of tokens.

    Accepted shapes:
    - string: split on whitespace,
    - list/tuple of strings: returned as list,
    - empty/None: returns [] (but this helper is only called on non-None).
    """
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        return value.split()

    # Assume it's already a sequence of strings
    return list(value)


@dataclass
class PassiveEventConstruction:
    """
    Language-agnostic passive event construction.

    Interface
    ---------
    def realize(
        slots: Mapping[str, Any],
        lang_profile: Mapping[str, Any],
        morph: Any,
    ) -> Dict[str, Any]

    Expected `slots` keys:
    - "patient_np"  : str | List[str] (required)
    - "verb_lemma"  : str            (required)
    - "agent_np"    : str | List[str] (optional; may be omitted for agentless passives)
    - "tense"       : str (e.g. "past", "present") [optional, default "past"]
    - "polarity"    : str (e.g. "affirmative", "negative") [optional, default "affirmative"]
    - "adverbials"  : List[str | List[str]] (optional; e.g. ["in 1903", ["in", "Paris"]])

    Expected `lang_profile["passive"]` keys (all optional):
    - "agent_marker"    : str  (e.g. "by", "", a case particle, etc.)
    - "agent_position"  : "postverb" | "preverb" | "final"
    - "subject_position": "preverb" | "postverb"
    - "allow_agentless" : bool (default: True)

    The `morph` object may provide:
    - make_verb_form(lemma: str, *, voice: str, tense: str, polarity: str) -> str
      If missing, the lemma is used directly.
    """

    id: str = "PASSIVE_EVENT"

    # ------------------------------------------------------------------ #
    # Core realization                                                   #
    # ------------------------------------------------------------------ #

    def realize(
        self,
        slots: Mapping[str, Any],
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
        # --- Extract required slots ---
        try:
            patient_raw = slots["patient_np"]
        except KeyError as e:
            raise KeyError("PASSIVE_EVENT requires 'patient_np' in slots") from e

        try:
            verb_lemma = slots["verb_lemma"]
        except KeyError as e:
            raise KeyError("PASSIVE_EVENT requires 'verb_lemma' in slots") from e

        patient_tokens = _normalize_tokens(patient_raw)

        # --- Optional slots ---
        agent_raw: Optional[TokensLike] = slots.get("agent_np")
        tense: str = slots.get("tense", "past")
        polarity: str = slots.get("polarity", "affirmative")
        adverbials_raw = slots.get("adverbials", [])

        # Normalize adverbials into list[list[str]]
        adverbial_chunks: List[List[str]] = []
        for adv in adverbials_raw:
            adverbial_chunks.append(_normalize_tokens(adv))

        # --- Language profile for passive ---
        passive_cfg: Mapping[str, Any] = lang_profile.get("passive", {}) or {}

        agent_marker: str = passive_cfg.get("agent_marker", "by")
        agent_position: str = passive_cfg.get("agent_position", "postverb")
        subject_position: str = passive_cfg.get("subject_position", "preverb")
        allow_agentless: bool = passive_cfg.get("allow_agentless", True)

        # --- Morphology: build verb form (or fallback to lemma) ---
        verb_form = self._make_verb_form(
            morph=morph,
            lemma=verb_lemma,
            tense=tense,
            polarity=polarity,
        )
        verb_tokens = verb_form.split()

        # --- Build agent phrase, if present / required ---
        agent_tokens: Optional[List[str]] = None
        if agent_raw is not None:
            base_agent = _normalize_tokens(agent_raw)
            if agent_marker:
                agent_tokens = [agent_marker] + base_agent
            else:
                agent_tokens = base_agent
        else:
            # No explicit agent supplied
            if not allow_agentless:
                # Language profile demands an agent; in the absence of data,
                # we just omit it but mark that it's missing.
                agent_tokens = None

        # --- Compose final token sequence according to positions ---
        tokens: List[str] = []

        # Subject (patient) before verb?
        if subject_position == "preverb":
            tokens.extend(patient_tokens)
            tokens.extend(verb_tokens)
        else:  # subject_position == "postverb"
            tokens.extend(verb_tokens)
            tokens.extend(patient_tokens)

        # Agent phrase placement
        if agent_tokens:
            if agent_position == "preverb":
                tokens = agent_tokens + tokens
            elif agent_position == "postverb":
                # already placed verb; insert agent after verb block
                # Here we simply append, assuming verb immediately precedes.
                tokens.extend(agent_tokens)
            elif agent_position == "final":
                # final position after everything else
                # We'll append after adverbials.
                pass  # handled below as "final"
            else:
                # Unknown setting → default to postverb
                tokens.extend(agent_tokens)

        # Adverbials
        for chunk in adverbial_chunks:
            tokens.extend(chunk)

        # If agent position is explicitly final, add it here
        if agent_tokens and agent_position == "final":
            tokens.extend(agent_tokens)

        # --- Build result structure ---
        text = " ".join(tokens)

        result: Dict[str, Any] = {
            "construction_id": self.id,
            "tokens": tokens,
            "text": text,
            "verb": verb_form,
            "roles": {
                "patient": patient_tokens,
                "agent": agent_tokens,
            },
            "meta": {
                "tense": tense,
                "polarity": polarity,
                "subject_role": "patient",
                "agent_included": agent_tokens is not None,
            },
        }
        return result

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_verb_form(
        morph: Any,
        lemma: str,
        *,
        tense: str,
        polarity: str,
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
                )
            )
        # Fallback: no dedicated verb form builder; use lemma.
        return lemma


__all__ = ["PassiveEventConstruction"]
