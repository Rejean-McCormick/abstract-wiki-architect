# morphology\isolating.py
"""
ISOLATING MORPHOLOGY MODULE
---------------------------

Family-level morphology helpers for isolating / analytic languages
(e.g. Mandarin, Vietnamese, various creoles, some West African languages).

Goals:
- Provide reusable primitives for:
  - Noun phrase realization (classifiers, plural particles, possessive linkers).
  - Adjective + noun ordering.
  - Simple verb realization with TAM and negation particles.
- Keep all language-specific quirks in the JSON config, not in code.

This module deliberately does NOT:
- Choose clause-level word order (that’s the construction layer’s job).
- Decide which construction to use (existential vs possession, etc.).
- Implement any inflectional morphology beyond particle concatenation.

----------------------------------------------------------------------
CONFIGURATION SHAPE (TYPICAL)
----------------------------------------------------------------------

A language card for an isolating language might look like:

{
  "syntax": {
    "use_spaces": false,
    "requires_classifier": true,
    "adjective_order": "pre",          # "pre" or "post"
    "verbal_pattern": "neg_tam_verb"   # or "verb_tam_neg", "tam_verb_neg"
  },
  "articles": {
    "indefinite": "一"                  # optional; can be empty
  },
  "classifiers": {
    "default": "个",
    "person": "位",
    "honorific": "位"
  },
  "particles": {
    "plural": "们",
    "possession": "的",
    "negation": "不",
    "tam": {
      "past": "了",
      "prog": "在",
      "future": "将"
    }
  }
}

The exact inventory is up to each language; this module only assumes
these *keys* may exist and falls back gracefully when they don’t.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, List


class IsolatingMorphology:
    """
    Morphology engine for Isolating / Analytic languages.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._syntax = config.get("syntax", {})
        self._articles = config.get("articles", {})
        self._classifiers = config.get("classifiers", {})
        self._particles = config.get("particles", {})

    # -------------------------------------------------------------------
    # Small config utilities
    # -------------------------------------------------------------------

    def _get_config(self, path: str, default: Any = None) -> Any:
        """
        Safe nested getter: "particles.plural" -> config["particles"]["plural"].

        Args:
            path: Dot-separated path.
            default: Fallback value if path is missing.

        Returns:
            The config value or default.
        """
        node: Any = self.config
        for key in path.split("."):
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def _uses_spaces(self) -> bool:
        """
        Whether this language writes tokens with spaces.

        Most Sinitic-like configs will set this to False; languages written with
        Latin script will usually set it to True.
        """
        return bool(self._syntax.get("use_spaces", False))

    def _join(self, tokens: List[str]) -> str:
        """
        Join surface tokens into a single string, respecting the script setting.
        """
        tokens = [t for t in tokens if t]
        if not tokens:
            return ""
        if self._uses_spaces():
            return " ".join(tokens)
        return "".join(tokens)

    # -------------------------------------------------------------------
    # Classifiers and noun core
    # -------------------------------------------------------------------

    def _select_classifier(
        self,
        features: Dict[str, Any],
    ) -> Optional[str]:
        """
        Select an appropriate classifier based on semantic hints in `features`.

        Feature hints (all optional):
        - classifier_type: explicit classifier key (e.g. "person", "book").
        - is_human: bool
        - honorific: bool

        Returns:
            A classifier string or None if none is applicable.
        """
        if not self._classifiers:
            return None

        # 1. Explicit override
        explicit = features.get("classifier_type")
        if explicit and explicit in self._classifiers:
            return self._classifiers[explicit]

        # 2. Honorific human
        if features.get("honorific") and "honorific" in self._classifiers:
            return self._classifiers["honorific"]

        # 3. Generic person
        if features.get("is_human") and "person" in self._classifiers:
            return self._classifiers["person"]

        # 4. Default fallback
        if "default" in self._classifiers:
            return self._classifiers["default"]

        return None

    def realize_noun_core(
        self,
        lemma: str,
        features: Dict[str, Any],
    ) -> str:
        """
        Realize the *core* noun phrase (without adjectives or possession).

        This handles:
        - Optional numerals and classifiers.
        - Optional plural particles.
        - Optional indefinite article equivalents.

        Feature keys (all optional, defaults are sensible):
        - number: "sg" | "pl"                   (default "sg")
        - definiteness: "bare" | "indef" | "def" (default "bare")
        - quantity: int (if present, overrides simple sg/pl logic)
        - is_human: bool
        - honorific: bool
        - classifier_type: str
        - use_classifier: bool (override)
        - use_plural_particle: bool (override)
        """
        lemma = lemma.strip()
        if not lemma:
            return ""

        number = features.get("number", "sg")
        definiteness = features.get("definiteness", "bare")

        requires_classifier = bool(self._syntax.get("requires_classifier", False))
        indefinite_article = self._articles.get("indefinite", "")
        plural_particle = self._particles.get("plural", "")

        # Classifier usage override
        use_classifier = features.get("use_classifier")
        if use_classifier is None:
            use_classifier = requires_classifier

        # Plural particle usage override
        use_plural_particle = features.get("use_plural_particle")
        if use_plural_particle is None:
            # Default heuristic: humans often accept plural particles, others not.
            use_plural_particle = bool(
                features.get("is_human", False) and plural_particle
            )

        quantity = features.get("quantity")
        parts: List[str] = []

        # 1. Explicit numeric quantity: "NUM CL N"
        if quantity is not None:
            quantity_str = str(quantity)
            parts.append(quantity_str)
            if use_classifier:
                clf = self._select_classifier(features)
                if clf:
                    parts.append(clf)
            parts.append(lemma)
            return self._join(parts)

        # 2. Indefinite singular with classifier: "INDEF CL N"
        if definiteness == "indef" and number == "sg" and use_classifier:
            clf = self._select_classifier(features)
            if indefinite_article:
                parts.append(indefinite_article)
            if clf:
                parts.append(clf)
            parts.append(lemma)
            return self._join(parts)

        # 3. Plural with particle: "N + PL"
        if number == "pl" and use_plural_particle and plural_particle:
            return lemma + plural_particle

        # 4. Bare noun (most common fallback)
        return lemma

    # -------------------------------------------------------------------
    # Adjectives and possessives
    # -------------------------------------------------------------------

    def realize_adjective_sequence(
        self,
        adjectives: List[str],
        noun_np: str,
    ) -> str:
        """
        Combine adjectives and noun according to adjective order settings.

        - "pre":  ADJ1 ADJ2 N
        - "post": N ADJ1 ADJ2
        """
        adjectives = [a.strip() for a in adjectives if a and a.strip()]
        noun_np = noun_np.strip()
        if not adjectives:
            return noun_np

        order = self._syntax.get("adjective_order", "pre")
        if order == "post":
            tokens = [noun_np] + adjectives
        else:
            tokens = adjectives + [noun_np]

        return self._join(tokens)

    def realize_possessive(
        self,
        owner_np: str,
        possessed_np: str,
        omit_particle_when_close: bool = False,
    ) -> str:
        """
        Realize a possessive NP: OWNER + POSSESSIVE_PARTICLE + POSSESSED.

        For Mandarin-like patterns: "玛丽 的 老师".

        Args:
            owner_np:
                Already-realized possessor NP.
            possessed_np:
                Already-realized possessed NP.
            omit_particle_when_close:
                Some analytic languages omit the possessive particle in tight
                compounds. If True, we just juxtapose OWNER and POSSESSED.

        Returns:
            Combined NP as a surface string.
        """
        owner_np = owner_np.strip()
        possessed_np = possessed_np.strip()
        if not owner_np:
            return possessed_np
        if not possessed_np:
            return owner_np

        possession_particle = self._particles.get("possession", "")

        if omit_particle_when_close or not possession_particle:
            # Simple juxtaposition
            return self._join([owner_np, possessed_np])

        return self._join([owner_np, possession_particle, possessed_np])

    # -------------------------------------------------------------------
    # High-level NP helper
    # -------------------------------------------------------------------

    def realize_noun_phrase(
        self,
        lemma: str,
        features: Optional[Dict[str, Any]],
    ) -> str:
        """
        Realize a full noun phrase, including:
        - core noun (with quantity, classifier, plural particle),
        - optional adjectives,
        - optional possessor.

        Features (optional keys, in addition to those used by realize_noun_core):
        - adjectives: list[str] of already-realized adjectives
        - possessor_np: str (an already-realized NP for the possessor)
        - omit_possessive_particle: bool
        """
        if features is None:
            features = {}

        adjectives = features.get("adjectives") or []
        possessor = features.get("possessor_np")

        # 1. Core NP
        core_np = self.realize_noun_core(lemma, features)

        # 2. Adjectives
        if adjectives:
            core_np = self.realize_adjective_sequence(adjectives, core_np)

        # 3. Possessive
        if possessor:
            core_np = self.realize_possessive(
                possessor,
                core_np,
                omit_particle_when_close=features.get(
                    "omit_possessive_particle",
                    False,
                ),
            )

        return core_np

    # -------------------------------------------------------------------
    # Verbs with TAM and negation particles
    # -------------------------------------------------------------------

    def realize_verb(
        self,
        lemma: str,
        features: Optional[Dict[str, Any]],
    ) -> str:
        """
        Realize a verb with optional TAM and negation particles.

        This is deliberately simple and particle-based, suitable for many
        isolating languages.

        Features (all optional):
        - tense: str  (e.g. "past", "future")
        - aspect: str (e.g. "prog", "perf")
        - mood: str   (e.g. "irrealis")
        - polarity: "pos" | "neg" (default "pos")

        Config expectations:
        - particles.negation: string or empty
        - particles.tam: { key -> particle }
        - syntax.verbal_pattern:
            - "neg_tam_verb"  (NEG + TAM* + V) [default]
            - "verb_tam_neg"  (V + TAM* [+ NEG at start])
            - "tam_verb_neg"  (TAM* + V [+ NEG at end])
        """
        if features is None:
            features = {}

        lemma = lemma.strip()
        if not lemma:
            return ""

        tense = features.get("tense")
        aspect = features.get("aspect")
        mood = features.get("mood")
        polarity = features.get("polarity", "pos")

        tam_particles = self._particles.get("tam", {})
        neg_particle = self._particles.get("negation", "")
        pattern = self._syntax.get("verbal_pattern", "neg_tam_verb")

        # Collect TAM particles (order: tense → aspect → mood)
        tam_tokens: List[str] = []
        if tense and tense in tam_particles:
            tam_tokens.append(tam_particles[tense])
        if aspect and aspect in tam_particles:
            tam_tokens.append(tam_particles[aspect])
        if mood and mood in tam_particles:
            tam_tokens.append(tam_particles[mood])

        verb_token = lemma
        neg_token = neg_particle if polarity == "neg" and neg_particle else ""

        tokens: List[str] = []

        if pattern == "verb_tam_neg":
            # V TAM* (NEG at start if present)
            # Example: NEG + V + TAM
            if neg_token:
                tokens.append(neg_token)
            tokens.append(verb_token)
            tokens.extend(tam_tokens)

        elif pattern == "tam_verb_neg":
            # TAM* V (NEG at end)
            tokens.extend(tam_tokens)
            tokens.append(verb_token)
            if neg_token:
                tokens.append(neg_token)

        else:
            # Default: "neg_tam_verb" → NEG TAM* V
            if neg_token:
                tokens.append(neg_token)
            tokens.extend(tam_tokens)
            tokens.append(verb_token)

        return self._join(tokens)
