# app/core/ports/planner_port.py
from __future__ import annotations

from typing import Protocol, Sequence, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from app.core.domain.planning.planned_sentence import PlannedSentence


# Intentionally broad during migration:
# the planner should accept already-normalized internal frame/domain objects
# without forcing the port to depend on one specific frame implementation.
FrameInput = object
PlanningDomain = str


@runtime_checkable
class PlannerPort(Protocol):
    """
    Canonical planner-side port for the planner-first generation runtime.

    The planner is responsible for transforming one or more normalized
    semantic/domain frames into sentence-level planning objects that are
    still backend-neutral. Its output is consumed downstream by the
    ConstructionPlan assembly layer, then lexical resolution, then the
    final realizer.

    Responsibilities:
        - preserve or intentionally reorder semantic content,
        - choose / finalize `construction_id`,
        - package content into one or more sentences,
        - assign discourse-facing metadata such as topic/focus,
        - remain renderer-agnostic.

    Non-responsibilities:
        - selecting renderer backends,
        - building GF ASTs,
        - performing lexical resolution,
        - doing morphology/inflection,
        - producing final surface strings.
    """

    def plan(
        self,
        frames: Sequence[FrameInput],
        *,
        lang_code: str,
        domain: PlanningDomain = "auto",
    ) -> list["PlannedSentence"]:
        """
        Produce sentence-level discourse plans from semantic frames.

        Args:
            frames:
                Normalized internal frame/domain objects. These may originate
                from API request normalization, semantic frame adapters, or
                bridge layers such as `frame_to_plan`.
            lang_code:
                Target language code used for language-aware planning decisions.
                This is planning-time language awareness, not realization.
            domain:
                Optional planning domain hint. The default `"auto"` allows the
                implementation to infer the domain from the incoming frames.

        Returns:
            A non-empty or empty list of `PlannedSentence` objects, depending on
            whether the input yields realizable sentence plans.

        Contract:
            - Output must be backend-neutral.
            - Output must not contain renderer-specific AST ownership.
            - Output should preserve enough metadata for downstream
              ConstructionPlan assembly and debugging.
            - The planner may intentionally reorder or package content when that
              is part of discourse planning; it must not silently change the
              underlying meaning.

        Notes:
            This interface is synchronous by design. Planning should remain a
            pure, deterministic core operation unless a concrete adapter has a
            compelling reason to layer async behavior outside this port.
        """
        ...
        

__all__ = [
    "FrameInput",
    "PlanningDomain",
    "PlannerPort",
]