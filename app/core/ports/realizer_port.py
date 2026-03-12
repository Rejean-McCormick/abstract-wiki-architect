# app/core/ports/realizer_port.py
from __future__ import annotations

"""
Canonical planner-to-renderer port.

This module defines the backend-agnostic realization boundary for the
construction-centered runtime:

    ConstructionPlan -> SurfaceResult

Realizers are backend adapters (for example GF, family-engine, or safe-mode
adapters). They consume a canonical construction plan and produce a canonical
surface result. They do not own planning, construction choice, or lexical
classification.

Migration note
--------------
Some existing code still uses the legacy frame-based engine path
(`IGrammarEngine.generate(lang_code, frame) -> Sentence`). That path is a
compatibility layer. The authoritative realizer contract defined here targets
`ConstructionPlan -> SurfaceResult`.

Implementation note
-------------------
`ConstructionPlan` and `SurfaceResult` are imported only for type checking.
During the migration batch, sibling runtime modules may exist before their
final classes are populated, so this port remains import-safe at runtime.
"""

from typing import Any, Literal, Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from app.core.domain.models import SurfaceResult
    from app.core.domain.planning.construction_plan import ConstructionPlan
else:  # pragma: no cover - runtime import safety during staged migration
    ConstructionPlan = Any
    SurfaceResult = Any


RealizerSupportStatus = Literal[
    "full",
    "partial",
    "fallback_only",
    "unsupported",
]


@runtime_checkable
class RealizerPort(Protocol):
    """
    Canonical renderer / realizer boundary.

    A realizer implementation MUST:
    - consume only a `ConstructionPlan` as renderer input,
    - preserve the selected `construction_id`,
    - avoid mutating the incoming plan,
    - return a `SurfaceResult`,
    - make fallback behavior explicit in result/debug metadata.

    A realizer MAY fail when the plan is unsupported, incomplete, or
    insufficiently lexicalized. It MUST NOT silently reinterpret the plan as a
    different construction.
    """

    async def realize(self, construction_plan: "ConstructionPlan") -> "SurfaceResult":
        """
        Produce a surface result from a canonical construction plan.
        """
        ...


@runtime_checkable
class RealizerCapabilitiesPort(RealizerPort, Protocol):
    """
    Optional capability/introspection helpers for dispatch and QA.

    These methods are intentionally separate from `realize(...)` so orchestration
    layers can perform cheap support checks before attempting full realization.
    """

    def supports(self, construction_id: str, lang_code: str) -> bool:
        """
        Return True iff this realizer can attempt the given
        `(construction_id, lang_code)` pair.

        This check SHOULD be cheap and MUST NOT trigger full generation.
        """
        ...

    def get_support_status(
        self,
        construction_id: str,
        lang_code: str,
    ) -> RealizerSupportStatus:
        """
        Return a coarse support level for dispatch, tooling, and debug output.

        Recommended values:
        - "full"
        - "partial"
        - "fallback_only"
        - "unsupported"
        """
        ...


@runtime_checkable
class NamedRealizerPort(RealizerPort, Protocol):
    """
    Optional identity helper.

    The backend name should be stable and machine-readable so it can appear in
    debug metadata and regression tooling.
    """

    @property
    def backend_name(self) -> str:
        """
        Stable backend identifier such as:
        - "gf"
        - "family"
        - "safe_mode"
        - "compat"
        """
        ...


# Compatibility aliases:
# - docs prefer `RealizerPort`
# - parts of the codebase historically prefer `I*` names for ports
IRealizerPort = RealizerPort
ICapabilityAwareRealizerPort = RealizerCapabilitiesPort
INamedRealizerPort = NamedRealizerPort

__all__ = [
    "RealizerSupportStatus",
    "RealizerPort",
    "RealizerCapabilitiesPort",
    "NamedRealizerPort",
    "IRealizerPort",
    "ICapabilityAwareRealizerPort",
    "INamedRealizerPort",
]