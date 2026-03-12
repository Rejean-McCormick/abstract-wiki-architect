# app/core/ports/lexical_resolver_port.py
"""
Canonical lexical-resolution port.

This module defines the shared runtime boundary between planning and realization
for lexical resolution. The canonical effect is:

    ConstructionPlan -> lexicalized ConstructionPlan

Implementations may also expose helper methods that operate on a whole slot map
or a single slot during migration, but renderers should consume the lexicalized
plan rather than re-running hidden lexical logic.

Design goals:
- backend-agnostic
- migration-friendly
- explicit provenance / confidence / fallback metadata
- deterministic, testable contracts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.core.domain.planning.construction_plan import ConstructionPlan
    from app.core.domain.planning.slot_map import SlotMap


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """
    Structured result for resolving one lexicalized slot.

    This object is intentionally backend-agnostic and JSON-friendly. It can be
    stored in `construction_plan.lexical_bindings`, copied into `debug_info`,
    or used directly by helper-oriented tests.

    Recommended `kind` values:
    - "entity"
    - "lexeme"
    - "literal"
    - "raw"
    - "unresolved"
    """

    slot_name: str
    input_value: Any
    resolved_value: Any
    kind: str = "unknown"
    source: str = "unknown"
    confidence: float = 0.0
    fallback_used: bool = False
    unresolved: bool = False
    surface_hint: str | None = None
    notes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        confidence = float(self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("ResolutionResult.confidence must be between 0.0 and 1.0")

        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "notes", tuple(self.notes))

    def as_dict(self) -> dict[str, Any]:
        """
        Return a stable JSON-friendly representation for debug metadata,
        lexical bindings, or API mapping layers.
        """
        return {
            "slot_name": self.slot_name,
            "input_value": self.input_value,
            "resolved_value": self.resolved_value,
            "kind": self.kind,
            "source": self.source,
            "confidence": self.confidence,
            "fallback_used": self.fallback_used,
            "unresolved": self.unresolved,
            "surface_hint": self.surface_hint,
            "notes": list(self.notes),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class LexicalResolutionOptions:
    """
    Optional policy bag for resolver implementations.

    These options are intentionally generic so they can be derived from
    `construction_plan.metadata`, request-level generation flags, or adapter-
    specific settings without leaking backend-specific types into the port.
    """

    prefer_existing_ids: bool = True
    allow_raw_fallback: bool = True
    allow_cross_language_fallback: bool = True
    strict: bool = False
    debug: bool = False
    hints: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "prefer_existing_ids": self.prefer_existing_ids,
            "allow_raw_fallback": self.allow_raw_fallback,
            "allow_cross_language_fallback": self.allow_cross_language_fallback,
            "strict": self.strict,
            "debug": self.debug,
            "hints": dict(self.hints),
        }


@runtime_checkable
class LexicalResolverPort(Protocol):
    """
    Canonical lexical-resolution port.

    Implementations must preserve:
    - construction identity
    - language identity
    - slot names
    - sentence meaning

    Implementations should enrich lexicalized slots with stable refs, provenance,
    confidence, and explicit fallback metadata where needed.
    """

    async def resolve(
        self,
        construction_plan: ConstructionPlan,
        *,
        lang_code: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
    ) -> ConstructionPlan:
        """
        Resolve lexicalized slots for an entire construction plan.

        Args:
            construction_plan:
                Planner-produced canonical runtime contract.
            lang_code:
                Optional override. If omitted, implementations should prefer the
                language already carried by the plan.
            generation_options:
                Optional runtime policy overrides. Implementations may merge
                these with options already attached to the plan.

        Returns:
            A lexicalized `ConstructionPlan`.

        Required behavior:
        - preserve `construction_id`
        - preserve `lang_code` semantics
        - preserve slot names
        - populate lexical bindings when supported by the plan model
        - record fallback metadata explicitly
        - never return renderer-specific lexical objects as the public contract
        """
        ...


@runtime_checkable
class SlotMapLexicalResolverPort(Protocol):
    """
    Optional migration helper for resolvers that operate at slot-map level.

    The canonical runtime boundary remains full-plan resolution. This helper is
    provided so migration code can keep lexical logic out of renderers even
    before every caller is upgraded to full `ConstructionPlan` orchestration.
    """

    async def resolve_slot_map(
        self,
        slot_map: SlotMap,
        *,
        lang_code: str,
        construction_id: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
    ) -> SlotMap:
        """
        Resolve a whole slot map into stable entity / lexeme / literal forms.

        Implementations should preserve slot names and avoid silently changing
        semantic categories.
        """
        ...


@runtime_checkable
class SlotLexicalResolverPort(Protocol):
    """
    Optional helper for deterministic single-slot resolution.

    Useful for tests, incremental migration, and construction-sensitive lexical
    resolution where the caller already knows the slot name and context.
    """

    async def resolve_slot(
        self,
        *,
        lang_code: str,
        construction_id: str,
        slot_name: str,
        slot_value: object,
        generation_options: Mapping[str, Any] | None = None,
    ) -> ResolutionResult:
        """
        Resolve one slot deterministically.

        Returns:
            A backend-agnostic `ResolutionResult`.
        """
        ...


@runtime_checkable
class LexicalResolverHelpers(Protocol):
    """
    Optional fine-grained helper interface.

    These helpers are intentionally not required by the canonical port, but they
    are useful for adapters that separate entity resolution from generic lexeme
    lookup internally.
    """

    async def resolve_entity(
        self,
        value: object,
        *,
        lang_code: str,
        generation_options: Mapping[str, Any] | None = None,
    ) -> ResolutionResult:
        """
        Resolve an entity-like value to a stable entity-oriented result.
        """
        ...

    async def resolve_lexeme(
        self,
        value: object,
        *,
        lang_code: str,
        pos: str | None = None,
        generation_options: Mapping[str, Any] | None = None,
    ) -> ResolutionResult:
        """
        Resolve a predicate-like or lexeme-like value to a stable lexeme result.
        """
        ...


# Compatibility alias for codebases that prefer the "I*" naming style.
ILexicalResolverPort = LexicalResolverPort


__all__ = [
    "ResolutionResult",
    "LexicalResolutionOptions",
    "LexicalResolverPort",
    "SlotMapLexicalResolverPort",
    "SlotLexicalResolverPort",
    "LexicalResolverHelpers",
    "ILexicalResolverPort",
]