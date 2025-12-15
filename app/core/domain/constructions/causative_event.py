# constructions\causative_event.py
"""
CAUSATIVE EVENT CONSTRUCTION

Language-agnostic pattern for causative statements like:

    "X made Y leave."
    "Her discoveries made this possible."
    "The decision caused delays."

This construction separates:

- CAUSER (the entity that causes)
- CAUSEE (the entity that undergoes / performs the caused event)
- RESULT_EVENT (an embedded verb phrase, possibly with an object)

It delegates morphology to `morph_api` and overall phrasing to
`lang_profile["causative"]`, via templates.

Typical English-like realizations:

    {causer} {cause_verb} {causee} to {result_verb} {result_object}
    {causer} {cause_verb} {result_event}

Depending on the language, the causative may be:

- Periphrastic (e.g. "make", "cause", "let" + embedded verb)
- Morphological (verb stem + causative affix)
- Mixed (special verbs for certain predicates)

We support both, using:

- `lang_profile["causative"]["strategy"]`:
    - "periphrastic" (default)
    - "morphological"
- Optional `morph_api.realize_causative(...)` for morphological strategies.
"""

from typing import Any, Dict, Optional, Union

from .base import BaseConstruction  # Expected BaseConstruction interface

NPInput = Union[str, Dict[str, Any]]


class CausativeEventConstruction(BaseConstruction):
    """
    CAUSATIVE_EVENT

    Expected `slots`:

        slots = {
            # Core roles:
            "causer": NPInput,                # the entity causing
            "causee": NPInput | None,         # the entity being caused (optional)
            "result_verb_lemma": str,         # embedded verb (e.g. "leave", "happen")
            "result_object": NPInput | None,  # optional object of the result verb

            # Verb/control:
            "cause_verb_lemma": str | None,   # override default cause verb (e.g. "make")
            "tense": str = "present",
            "polarity": str = "positive",

            # Optional: richer embedded event (if you don't want to use
            # result_verb_lemma/result_object):
            "embedded_event_surface": str | None
        }

    `lang_profile` may contain:

        "causative": {
            "strategy": "periphrastic" | "morphological",
            "cause_verb_lemma": "make",
            "template":
                "{causer} {cause_verb} {causee} to {result_verb} {result_object}",
            "template_no_causee":
                "{causer} {cause_verb} {result_event}",
            "template_no_result_object":
                "{causer} {cause_verb} {causee} to {result_verb}"
        }

    Placeholders supported in templates:

        - {causer}
        - {causee}
        - {cause_verb}
        - {result_verb}
        - {result_object}
        - {result_event}

    Any missing component is replaced by an empty string, and spaces are normalized.
    """

    id: str = "CAUSATIVE_EVENT"

    def realize(
        self,
        slots: Dict[str, Any],
        lang_profile: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        causative_cfg = lang_profile.get("causative", {})
        strategy = causative_cfg.get("strategy", "periphrastic")

        # Realize core participants
        causer = self._realize_np(slots.get("causer"), morph_api)
        causee = self._realize_np(slots.get("causee"), morph_api)

        # Realize embedded event either from a pre-built surface or by
        # combining result_verb + result_object.
        embedded_event_surface = self._realize_embedded_event(slots, morph_api)

        if strategy == "morphological" and hasattr(morph_api, "realize_causative"):
            return self._realize_morphological(
                causer=causer,
                causee=causee,
                embedded_event_surface=embedded_event_surface,
                slots=slots,
                lang_profile=lang_profile,
                morph_api=morph_api,
            )

        # Default: periphrastic causative using a cause verb + embedded event
        return self._realize_periphrastic(
            causer=causer,
            causee=causee,
            embedded_event_surface=embedded_event_surface,
            slots=slots,
            lang_profile=lang_profile,
            morph_api=morph_api,
        )

    # ------------------------------------------------------------------ #
    # Periphrastic causative ("make", "cause", "let" + embedded event)
    # ------------------------------------------------------------------ #

    def _realize_periphrastic(
        self,
        causer: str,
        causee: str,
        embedded_event_surface: str,
        slots: Dict[str, Any],
        lang_profile: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        causative_cfg = lang_profile.get("causative", {})

        # Realize the cause verb
        cause_verb = self._realize_cause_verb(slots, lang_profile, morph_api)

        # Also expose result verb/object separately for template flexibility
        result_verb = self._realize_result_verb(slots, morph_api)
        result_object = self._realize_np(slots.get("result_object"), morph_api)

        # Choose template depending on presence of causee / result_object
        template = causative_cfg.get(
            "template",
            "{causer} {cause_verb} {causee} to {result_verb} {result_object}",
        )

        if not causee:
            template = causative_cfg.get(
                "template_no_causee",
                "{causer} {cause_verb} {result_event}",
            )

        elif not result_object and result_verb:
            template = causative_cfg.get(
                "template_no_result_object",
                "{causer} {cause_verb} {causee} to {result_verb}",
            )

        parts = {
            "causer": causer or "",
            "causee": causee or "",
            "cause_verb": cause_verb or "",
            "result_verb": result_verb or "",
            "result_object": result_object or "",
            "result_event": embedded_event_surface or "",
        }

        return _normalize_spaces(template.format(**parts))

    # ------------------------------------------------------------------ #
    # Morphological causative
    # ------------------------------------------------------------------ #

    def _realize_morphological(
        self,
        causer: str,
        causee: str,
        embedded_event_surface: str,
        slots: Dict[str, Any],
        lang_profile: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        """
        For languages with a morphological causative, we delegate to
        morph_api.realize_causative and then optionally place causer/causee
        according to basic word order.

        We assume morph_api.realize_causative has the signature:

            realize_causative(
                result_verb_lemma: str,
                features: Dict[str, Any]
            ) -> str

        and that it returns a causativized verb form like "döndür-" (tr) etc.
        """
        basic_word_order = lang_profile.get("basic_word_order", "SVO")

        result_verb_lemma = slots.get("result_verb_lemma", "")

        features = {
            "tense": slots.get("tense", "present"),
            "polarity": slots.get("polarity", "positive"),
        }

        if hasattr(morph_api, "realize_causative"):
            causative_verb = morph_api.realize_causative(result_verb_lemma, features)
        else:
            # Fallback: treat as a normal verb; this is not ideal but safe.
            causative_verb = self._realize_result_verb(slots, morph_api)

        # Basic S/O placement for a causative verb:
        #   CAUSER = syntactic subject
        #   CAUSEE = object or oblique (language-specific details not handled here)
        if basic_word_order in ("SVO", "SOV", "OSV", "OVS"):
            # S (causer) V (causative_verb) O (causee + embedded object phrase)
            components = [causer, causative_verb]
            if causee:
                components.append(causee)
            if embedded_event_surface:
                components.append(embedded_event_surface)
            return _normalize_spaces(" ".join(c for c in components if c))

        # VSO / VOS-like fallback
        components = [causative_verb, causer]
        if causee:
            components.append(causee)
        if embedded_event_surface:
            components.append(embedded_event_surface)
        return _normalize_spaces(" ".join(c for c in components if c))

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _realize_np(self, np_spec: Optional[NPInput], morph_api: Any) -> str:
        if not np_spec:
            return ""

        if isinstance(np_spec, str):
            return np_spec

        if isinstance(np_spec, dict):
            if hasattr(morph_api, "realize_np"):
                return morph_api.realize_np(np_spec)
            lemma = np_spec.get("lemma") or np_spec.get("surface") or ""
            return str(lemma)

        return str(np_spec)

    def _realize_cause_verb(
        self,
        slots: Dict[str, Any],
        lang_profile: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        causative_cfg = lang_profile.get("causative", {})
        default_lemma = causative_cfg.get("cause_verb_lemma", "make")

        cause_verb_lemma = slots.get("cause_verb_lemma") or default_lemma

        features = {
            "tense": slots.get("tense", "present"),
            "polarity": slots.get("polarity", "positive"),
        }

        if hasattr(morph_api, "realize_verb"):
            return morph_api.realize_verb(cause_verb_lemma, features)

        # Fallback: uninflected lemma
        return cause_verb_lemma

    def _realize_result_verb(
        self,
        slots: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        result_verb_lemma = slots.get("result_verb_lemma", "")
        if not result_verb_lemma:
            return ""

        features = {
            "tense": "infinitive",  # default; periphrastic constructions often use non-finite form
            "polarity": slots.get("polarity", "positive"),
        }

        if hasattr(morph_api, "realize_verb"):
            return morph_api.realize_verb(result_verb_lemma, features)

        return result_verb_lemma

    def _realize_embedded_event(
        self,
        slots: Dict[str, Any],
        morph_api: Any,
    ) -> str:
        """
        Build a surface for the embedded event, if the caller did not
        provide one explicitly.
        """
        explicit_surface = slots.get("embedded_event_surface")
        if explicit_surface:
            return explicit_surface

        result_verb = self._realize_result_verb(slots, morph_api)
        result_object = self._realize_np(slots.get("result_object"), morph_api)

        return _normalize_spaces(f"{result_verb} {result_object}".strip())


def _normalize_spaces(text: str) -> str:
    """
    Collapse multiple spaces and strip leading/trailing spaces.
    """
    return " ".join(text.split())
