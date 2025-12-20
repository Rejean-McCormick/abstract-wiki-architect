# app\core\domain\morphology\japonic.py
# morphology\japonic.py
"""
JAPONIC MORPHOLOGY MODULE
=========================

Family-specific morphology and particle handling for Japonic languages
(e.g. Japanese) within the layered architecture.

This module provides the morphology API expected by the construction
layer and the router:

    - JaponicMorphology(config)

      * realize_np(role: str, concept: dict) -> str
      * realize_verb(lemma: str, features: dict) -> str
      * normalize_whitespace(text: str) -> str
      * finalize_sentence(text: str) -> str

Design goals
------------

- Be *config-driven*:
  - Particles, verb forms, and syntactic style all come from the
    language profile (the `config` dict passed at construction).
- Be *defensive*:
  - If a configuration piece is missing, fall back to reasonable
    defaults and never crash on missing keys.
- Be *minimal but realistic*:
  - Enough behavior for typical Wikipedia-style bios
    (copula, existential, topic/subject/possessor marking),
    without trying to encode full Japanese morphology.

Expected config shape (illustrative, not strictly required):

    {
      "language_code": "ja",
      "family": "japonic",

      "syntax": {
        "style": "formal",        # or "plain", "polite"
        "use_spaces": false,
        "punctuation": "。"
      },

      "particles": {
        "topic": "は",
        "subject": "が",
        "genitive": "の"
      },

      "np_roles": {
        "subject":           {"particle": "が"},
        "topic":             {"particle": "は"},
        "possessor_oblique": {"particle": "には"},
        "rc_subject":        {"particle": "が"},
        "rc_head":           {"particle": ""}   # usually no particle
      },

      "lexicon": {
        "nouns": {
          "Marie Curie": "マリー・キュリー",
          "physicist": "物理学者",
          "Poland": "ポーランド",
          ...
        }
      },

      "verbs": {
        "copula": {
          "plain": "だ",
          "polite": "です",
          "formal": "である",
          "default": "である"
        },
        "exist": {
          "present_affirmative": "いる",
          "past_affirmative": "いた",
          "present_negative": "いない",
          "past_negative": "いなかった",
          "default": "いる"
        },
        "discover": {
          "past_affirmative": "発見した",
          "default": "発見する"
        },
        "lexicon": {
          # optional generic verb lexicon entries
        }
      }
    }

Concept objects
---------------

The `concept` dicts passed into `realize_np` are treated very flexibly
and defensively. Only a few fields are inspected:

    concept.get("surface")  # if present, used verbatim
    concept.get("lemma")    # fallback lexical key
    concept.get("name")     # fallback lexical key
    concept.get("label")    # fallback lexical key
    concept.get("owner")    # another concept -> genitive chain

Everything else is passed through to higher-level logic or ignored.

This is deliberate: the morphology layer should not be tightly coupled
to a single ontology schema.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


_PUNCTUATION_END = ("。", "！", "？", ".", "!", "?")


def _as_str(value: Any) -> str:
    """Best-effort conversion of a value to a string."""
    if isinstance(value, str):
        return value
    return str(value)


# ---------------------------------------------------------------------------
# JaponicMorphology
# ---------------------------------------------------------------------------


class JaponicMorphology:
    """Family-specific morphology utilities for Japonic languages."""

    # ------------------------------------------------------------------ #
    # Construction / configuration                                      #
    # ------------------------------------------------------------------ #

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the morphology helper with a Japonic language config.

        Args:
            config: Parsed JSON configuration for a specific Japonic
                    language (typically the language profile for "ja").
        """
        self.config = config or {}

        # Subsections (all optional)
        self._syntax: Dict[str, Any] = self.config.get("syntax", {}) or {}
        self._particles: Dict[str, Any] = self.config.get("particles", {}) or {}
        self._np_roles: Dict[str, Any] = self.config.get("np_roles", {}) or {}

        self._lexicon: Dict[str, Any] = self.config.get("lexicon", {}) or {}
        self._noun_lexicon: Dict[str, str] = (
            self._lexicon.get("nouns", {})
            if isinstance(self._lexicon.get("nouns"), dict)
            else {}
        )

        self._verbs: Dict[str, Any] = self.config.get("verbs", {}) or {}
        self._copula_cfg: Dict[str, Any] = (
            self._verbs.get("copula", {})
            if isinstance(self._verbs.get("copula"), dict)
            else {}
        )
        self._verb_lexicon: Dict[str, Any] = (
            self._verbs.get("lexicon", {})
            if isinstance(self._verbs.get("lexicon"), dict)
            else {}
        )

    # ------------------------------------------------------------------ #
    # Syntax-level configuration                                        #
    # ------------------------------------------------------------------ #

    def default_style(self) -> str:
        """
        Return the default copula/style label for this language.

        Falls back to "formal" if not explicitly configured.
        """
        style = self._syntax.get("style")
        if isinstance(style, str) and style:
            return style
        return "formal"

    def use_spaces(self) -> bool:
        """
        Whether this language prefers spaces between tokens.

        Japanese default: False.
        """
        val = self._syntax.get("use_spaces")
        if isinstance(val, bool):
            return val
        return False

    def punctuation(self) -> str:
        """
        Sentence-final punctuation string.

        Japanese default: "。"
        """
        punct = self._syntax.get("punctuation")
        if isinstance(punct, str) and punct:
            return punct
        return "。"

    # ------------------------------------------------------------------ #
    # Particles                                                          #
    # ------------------------------------------------------------------ #

    def topic_particle(self) -> str:
        """Return the topic marker (e.g. 'は')."""
        val = self._particles.get("topic")
        if isinstance(val, str) and val:
            return val
        return "は"

    def subject_particle(self) -> str:
        """Return the subject marker (e.g. 'が')."""
        val = self._particles.get("subject")
        if isinstance(val, str) and val:
            return val
        return "が"

    def genitive_particle(self) -> str:
        """Return the genitive/possessive marker (e.g. 'の')."""
        val = self._particles.get("genitive")
        if isinstance(val, str) and val:
            return val
        return "の"

    # ------------------------------------------------------------------ #
    # Copula and verb selection                                          #
    # ------------------------------------------------------------------ #

    def select_copula(self, style: Optional[str] = None) -> str:
        """
        Select the appropriate copula form for the requested style.

        Args:
            style:
                A style label such as "plain", "polite", or "formal".
                If None, use the language's default style from syntax,
                then fall back to "default" entry in the copula config.

        Returns:
            The copula string (e.g. "です", "だ", "である"), or an empty
            string if no copula is to be used.
        """
        if not isinstance(self._copula_cfg, dict):
            return ""

        style = style or self.default_style()

        # Exact style match
        candidate = self._copula_cfg.get(style)
        if isinstance(candidate, str) and candidate:
            return candidate

        # Fallback to 'default'
        default = self._copula_cfg.get("default")
        if isinstance(default, str) and default:
            return default

        # Final fallback: empty (no copula)
        return ""

    def _select_verb_from_entry(
        self, entry: Dict[str, Any], features: Dict[str, Any]
    ) -> str:
        """
        Given a verb entry and a feature bundle, pick the best surface form.

        Expected keys in entry (all optional):
            - combinations like "present_affirmative", "past_negative"
            - "present", "past"
            - "default"
            - "base"
        """
        if not isinstance(entry, dict):
            return ""

        tense = _as_str(features.get("tense", "present"))
        polarity = _as_str(features.get("polarity", "affirmative"))
        politeness = features.get("politeness") or features.get("formality")

        candidates = []

        # Most specific combinations first
        if politeness:
            candidates.append(f"{tense}_{polarity}_{politeness}")
        candidates.append(f"{tense}_{polarity}")
        candidates.append(tense)

        # Finally, generic fallbacks
        candidates.append("default")
        candidates.append("base")

        for key in candidates:
            val = entry.get(key)
            if isinstance(val, str) and val:
                return val

        # No match, but entry might still store a direct string
        if isinstance(entry.get("form"), str):
            return entry["form"]

        # Last resort: empty
        return ""

    def realize_verb(self, lemma: str, features: Dict[str, Any]) -> str:
        """
        Realize a verb form given a lemma and features.

        Behavior:
        - If lemma is "copula", delegate to `select_copula`.
        - Otherwise, look up lemma in `verbs[lemma]` or in
          `verbs.lexicon[lemma]` and select a form based on features.
        - If nothing is found, return the lemma as-is.
        """
        lemma = _as_str(lemma)

        # Copula as a special case
        if lemma == "copula":
            style = features.get("style")
            return self.select_copula(style=style)

        # Try main verbs config
        verb_entry = self._verbs.get(lemma)
        if isinstance(verb_entry, dict):
            form = self._select_verb_from_entry(verb_entry, features)
            if form:
                return form

        # Try verb lexicon
        lex_entry = self._verb_lexicon.get(lemma)
        if isinstance(lex_entry, dict):
            form = self._select_verb_from_entry(lex_entry, features)
            if form:
                return form
        elif isinstance(lex_entry, str):
            return lex_entry

        # Fallback: lemma string as-is
        return lemma

    # ------------------------------------------------------------------ #
    # Noun phrase realization                                            #
    # ------------------------------------------------------------------ #

    def _lookup_noun_surface(self, lemma: str) -> str:
        """Look up the noun surface form from the lexicon, with fallback."""
        if not lemma:
            return ""
        if lemma in self._noun_lexicon:
            val = self._noun_lexicon[lemma]
            if isinstance(val, str) and val:
                return val
        # Fallback to lemma itself
        return lemma

    def _realize_np_core(self, concept: Any) -> str:
        """
        Realize the core noun phrase for a concept, without particles.

        Rules (in priority order):
            1) If concept is not a dict: str(concept)
            2) If concept["surface"] exists: use it verbatim.
            3) Else use concept["lemma"] / ["name"] / ["label"] as
               lexical key, then look up in noun lexicon.
            4) If concept["owner"] exists (another concept), build a
               genitive chain: owner + の + head.
        """
        # Non-dict concepts: just stringify
        if not isinstance(concept, dict):
            return _as_str(concept)

        # Explicit surface override
        surface = concept.get("surface")
        if isinstance(surface, str) and surface:
            base = surface
        else:
            lemma = concept.get("lemma") or concept.get("name") or concept.get("label")
            base = self._lookup_noun_surface(_as_str(lemma))

        # Genitive chain if owner present
        owner = concept.get("owner")
        if owner:
            owner_np = self._realize_np_core(owner)
            base = self.attach_genitive(np_head=base, np_dependent=owner_np)

        return base

    def _attach_role_particle(self, np: str, role: str) -> str:
        """
        Attach a particle based on NP role configuration, with heuristics.

        - If config defines np_roles[role]["particle"], use that.
        - Otherwise:
            * if role == "subject" or role endswith "_subject": use subject particle.
            * if role == "topic": use topic particle.
            * else: no particle.
        """
        # Config-driven
        role_cfg = self._np_roles.get(role)
        particle: Optional[str] = None

        if isinstance(role_cfg, dict):
            particle = role_cfg.get("particle")

        if isinstance(particle, str) and particle:
            if self.use_spaces():
                return f"{np} {particle}"
            return f"{np}{particle}"

        # Heuristic fallbacks
        if role == "topic":
            return self.attach_topic(np)
        if role == "subject" or role.endswith("_subject"):
            return self.attach_subject(np)

        # Default: no particle
        return np

    def realize_np(self, role: str, concept: Any) -> str:
        """
        Realize a noun phrase with appropriate particles for a given role.

        Args:
            role:
                Logical role label (e.g. "subject", "possessor_oblique",
                "rc_subject", "rc_head", etc.). Interpreted according to
                the language profile's `np_roles` config, with fallbacks.
            concept:
                Concept object (dict or other) describing the entity.

        Returns:
            Surface NP string, possibly including a case/topic particle.
        """
        core = self._realize_np_core(concept)
        if not core:
            return ""
        return self._attach_role_particle(core, role)

    # ------------------------------------------------------------------ #
    # Particle helpers (public, may be used by other components)         #
    # ------------------------------------------------------------------ #

    def attach_topic(self, np: str) -> str:
        """
        Attach the topic particle to a noun phrase.

        Example:
            "マリー・キュリー" -> "マリー・キュリーは"
        """
        topic = self.topic_particle()
        if self.use_spaces():
            return f"{np} {topic}"
        return f"{np}{topic}"

    def attach_subject(self, np: str) -> str:
        """
        Attach the subject particle to a noun phrase.

        Example:
            "彼女" -> "彼女が"
        """
        subj = self.subject_particle()
        if self.use_spaces():
            return f"{np} {subj}"
        return f"{np}{subj}"

    def attach_genitive(self, np_head: str, np_dependent: str) -> str:
        """
        Attach a dependent noun phrase using the genitive particle.

        Example (Japanese):
            np_dependent = "フランス"
            np_head      = "物理学者"
            -> "フランスの物理学者"

        Args:
            np_head: The head noun phrase (the thing being described).
            np_dependent: The dependent noun phrase (owner/origin/etc.).

        Returns:
            Combined NP using the genitive particle.
        """
        gen = self.genitive_particle()
        if self.use_spaces():
            return f"{np_dependent} {gen} {np_head}"
        return f"{np_dependent}{gen}{np_head}"

    # ------------------------------------------------------------------ #
    # Whitespace / punctuation                                           #
    # ------------------------------------------------------------------ #

    def normalize_whitespace(self, text: str) -> str:
        """
        Normalize whitespace according to the language's spacing rules.

        - If `use_spaces` is False, all ASCII spaces are removed.
        - Otherwise, multiple spaces collapse to a single space and
          leading/trailing spaces are trimmed.
        """
        if not isinstance(text, str):
            return ""

        if not self.use_spaces():
            # Remove plain ASCII spaces; sufficient for our pipeline
            return text.replace(" ", "")

        parts = text.split()
        return " ".join(parts)

    def finalize_sentence(self, text: str) -> str:
        """
        Apply whitespace normalization and ensure final punctuation.

        Steps:
            1) Normalize whitespace.
            2) If the result already ends with a known punctuation mark,
               return as-is.
            3) Otherwise, append `self.punctuation()`.
        """
        base = self.normalize_whitespace(text)
        if not base:
            return base

        # Already properly terminated?
        for ch in _PUNCTUATION_END:
            if base.endswith(ch):
                return base

        return f"{base}{self.punctuation()}"
