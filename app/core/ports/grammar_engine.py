# app/core/ports/grammar_engine.py
from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from app.core.domain.models import Frame, Sentence

try:  # Runtime-safe during migration while the new contract files land.
    from app.core.domain.planning.construction_plan import ConstructionPlan
except Exception:  # pragma: no cover
    ConstructionPlan = Any  # type: ignore[assignment,misc]


FrameInput = Frame | Mapping[str, Any]


@runtime_checkable
class IGrammarEngine(Protocol):
    """
    Port for text realization backends.

    Canonical boundary:
        ConstructionPlan -> Sentence

    Temporary compatibility boundary:
        Frame -> Sentence

    Notes:
    - New orchestration should prefer `realize(construction_plan=...)`.
    - `generate(lang_code, frame)` remains only as a migration shim for
      legacy callers while planner-first orchestration is rolled out.
    - Any compatibility fallback should be made explicit in `Sentence.debug_info`.
    """

    async def realize(self, construction_plan: ConstructionPlan) -> Sentence:
        """
        Realize a lexicalized construction plan into surface text.

        Args:
            construction_plan:
                The planner-produced, construction-centric runtime contract.
                Implementations should treat it as immutable input.

        Returns:
            A Sentence containing the realized text plus structured debug metadata.

        Expected debug fields when available:
            - construction_id
            - renderer_backend / engine_backend
            - lang_code / resolved_language
            - fallback_used
            - backend_trace / ast (backend-specific, optional)

        Raises:
            LanguageNotFoundError:
                If the requested language/backend is unavailable.
            UnsupportedConstructionError:
                If the backend does not support the plan's construction.
            UnlexicalizedPlanError:
                If required lexical bindings are missing and fallback is disallowed.
            GrammarCompilationError:
                If the underlying grammar/engine fails internally.
        """
        ...

    async def generate(self, lang_code: str, frame: FrameInput) -> Sentence:
        """
        Legacy compatibility entrypoint.

        This method exists so older code paths can continue to function during
        migration. Implementations should prefer to normalize this call into the
        planner-first pipeline internally:

            frame -> planner/bridge -> ConstructionPlan -> realize()

        Args:
            lang_code:
                Target language code. Prefer normalized runtime codes.
            frame:
                A semantic Frame object or legacy dict-like frame payload.

        Returns:
            A Sentence object containing text and structured debug metadata.

        Migration rule:
            New code should not use this as the primary runtime boundary.
            If an adapter falls back to direct frame generation, that fallback
            must be machine-readable in `debug_info` (for example via
            `fallback_used=True` and a clear fallback reason).
        """
        ...

    def supports(self, construction_id: str, lang_code: str) -> bool:
        """
        Cheap capability probe.

        Args:
            construction_id:
                Canonical runtime construction identifier.
            lang_code:
                Target language code.

        Returns:
            True if the backend can attempt realization for this
            `(construction_id, lang_code)` pair, otherwise False.

        Notes:
            - This should be inexpensive.
            - It must not trigger full generation.
            - It is intended for dispatch/orchestration decisions.
        """
        ...

    async def get_supported_languages(self) -> list[str]:
        """
        Return language codes currently available to this backend.
        """
        ...

    async def reload(self) -> None:
        """
        Reload engine resources (for example after a new PGF build).
        """
        ...

    async def health_check(self) -> bool:
        """
        Return True iff the engine/backend is responsive and usable.
        """
        ...


# Compatibility alias for code that prefers the "Port" naming style.
GrammarEnginePort = IGrammarEngine

__all__ = [
    "FrameInput",
    "IGrammarEngine",
    "GrammarEnginePort",
]