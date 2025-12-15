# semantics\relational\opinion_evaluation_frame.py
"""
semantics/relational/opinion_evaluation_frame.py
===============================================

Opinion / evaluation frame.

This module defines a light-weight semantic frame for *attributed*
opinions or evaluations over some subject, for example:

    - "The film received positive reviews."
    - "Critics praised the performance."
    - "He is widely regarded as one of the greatest players."

The frame is intended to be used wherever we want to express that some
source (critics, scholars, the public, a particular reviewer, etc.)
evaluates a subject positively, negatively, or in a mixed way, possibly
with a scalar rating backing it (stars, scores, etc.).

Lexicalization (choice of verbs like "praise", "criticize", "consider",
and adverbs like "widely", "generally") is handled by the constructions
and engines; this module only defines the abstract data shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from semantics.types import Entity, TimeSpan


@dataclass
class OpinionFrame:
    """
    Attributed opinion / evaluation.

    Examples
    --------
        - "The film received positive reviews."
        - "Critics praised the performance."
        - "He is widely regarded as one of the greatest players."

    Semantics
    ---------
    * ``subject`` is the thing being evaluated (film, player, policy, etc.).
    * ``evaluator`` is who holds the opinion (critics, scholars, public, a
      specific person or organization). If omitted, engines may use generic
      wording ("it is widely regarded…").
    * ``aspect`` optionally narrows what is being evaluated ("performance",
      "design", "story", "policy", etc.).
    * ``polarity`` captures the overall sentiment:

          - "positive"
          - "negative"
          - "mixed"
          - (other project-specific codes are allowed but discouraged)

    * ``rating_value`` / ``rating_scale`` optionally back the opinion with
      a scalar rating ("8.5" on "out_of_10", "4" on "stars", etc.).
    * ``time`` and ``basis`` provide light-weight provenance for when and
      on what basis the opinion was formed ("reviews", "polls", etc.).
    * ``certainty`` and ``source_id`` are generic metadata used elsewhere
      in the system for weighting and tracing facts.
    """

    # Optional stable identifier for this fact (e.g. Wikidata statement id).
    id: Optional[str] = None

    # Core opinion structure
    evaluator: Optional[Entity] = None  # "critics", "scholars", "public", …
    subject: Entity = field(default_factory=Entity)  # thing being evaluated
    aspect: Optional[str] = None  # "performance", "design", "story", …

    # Overall polarity of the evaluation
    polarity: str = "positive"  # "positive", "negative", "mixed", …

    # Optional scalar rating backing the opinion
    rating_value: Optional[float] = None
    rating_scale: Optional[str] = None  # "out_of_10", "stars", …

    # Temporal anchoring and basis
    time: Optional[TimeSpan] = None
    basis: Optional[str] = None  # "reviews", "polls", "surveys", …

    # Confidence / provenance
    certainty: float = 1.0  # degree of support in the data
    source_id: Optional[str] = None  # pointer to upstream source / statement

    # Free-form extension bag
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["OpinionFrame"]
