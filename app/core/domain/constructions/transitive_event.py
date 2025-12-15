# constructions\transitive_event.py
"""
TRANSITIVE_EVENT CONSTRUCTION
-----------------------------

Language-agnostic clause pattern for transitive events (Subject-Verb-Object).

Examples:
    - "Marie Curie discovered radium." (SVO)
    - "Marie Curie radium discovered." (SOV - e.g. Japanese/Turkish)
    - "Discovered Marie Curie radium." (VSO - e.g. Celtic)

This construction handles:
- Realizing the Subject NP.
- Realizing the Object NP (with appropriate case marking via morph_api).
- Realizing the Verb (tense/aspect/polarity).
- Linearizing tokens based on `lang_profile["basic_word_order"]`.
"""

from typing import Any, Dict, List, Optional, Union

from .base import BaseConstruction

NPInput = Union[str, Dict[str, Any]]


class TransitiveEventConstruction(BaseConstruction):
    """
    Core transitive-event construction.

    Expected slots:
        slots = {
            "subject": NPInput,       # required
            "object": NPInput,        # required
            "verb_lemma": str,        # required
            "tense": str,             # optional (default: "present")
            "aspect": str,            # optional
            "polarity": str,          # optional
            "voice": str              # optional (default: "active")
        }

    Language Profile keys used:
        - "basic_word_order": "SVO" | "SOV" | "VSO" | "VOS" | "OVS" | "OSV"
    """

    id: str = "TRANSITIVE_EVENT"

    def realize(
        self,
        slots: Dict[str, Any],
        lang_profile: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        # 1. Realize Core Arguments
        subject_surface = self._realize_np(slots.get("subject"), "subject", morph_api)
        object_surface = self._realize_np(slots.get("object"), "object", morph_api)

        # 2. Realize Verb
        # We pass the subject surface or features if the morph engine needs
        # to handle agreement (though standard engine APIs typically take
        # features explicitly).
        verb_surface = self._realize_verb(slots, morph_api)

        # 3. Determine Word Order
        order = lang_profile.get("basic_word_order", "SVO").upper()
        tokens: List[str] = []

        if order == "SVO":
            tokens = [subject_surface, verb_surface, object_surface]
        elif order == "SOV":
            tokens = [subject_surface, object_surface, verb_surface]
        elif order == "VSO":
            tokens = [verb_surface, subject_surface, object_surface]
        elif order == "VOS":
            tokens = [verb_surface, object_surface, subject_surface]
        elif order == "OVS":
            tokens = [object_surface, verb_surface, subject_surface]
        elif order == "OSV":
            tokens = [object_surface, subject_surface, verb_surface]
        else:
            # Default fallback
            tokens = [subject_surface, verb_surface, object_surface]

        # 4. Join and Return
        # Filter out empty strings (e.g. if subject is dropped/pro-drop)
        return " ".join(t for t in tokens if t)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _realize_np(self, np_spec: Optional[NPInput], role: str, morph_api: Any) -> str:
        if not np_spec:
            return ""

        if isinstance(np_spec, str):
            return np_spec

        if isinstance(np_spec, dict):
            # Inject the semantic role (subject vs object) so the engine
            # can apply case (Accusative, etc.) if needed.
            features = np_spec.copy()
            # If features are nested in a 'features' key, update that instead
            if "features" in features and isinstance(features["features"], dict):
                features["features"]["role"] = role
            else:
                features["role"] = role

            if hasattr(morph_api, "realize_np"):
                return morph_api.realize_np(features)

            # Fallback
            lemma = np_spec.get("lemma") or np_spec.get("surface") or ""
            return str(lemma)

        return str(np_spec)

    def _realize_verb(
        self,
        slots: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        verb_lemma = slots.get("verb_lemma", "")
        if not verb_lemma:
            return ""

        features: Dict[str, Any] = {
            "tense": slots.get("tense", "present"),
            "aspect": slots.get("aspect", "simple"),
            "polarity": slots.get("polarity", "positive"),
            "voice": slots.get("voice", "active"),
            # In a full implementation, you might copy subject features here
            # for agreement (person/number/gender).
        }

        if hasattr(morph_api, "realize_verb"):
            return morph_api.realize_verb(verb_lemma, features)

        return verb_lemma
