from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator, Mapping, Protocol

__all__ = [
    "CANONICAL_CONSTRUCTION_ID_RE",
    "KNOWN_RUNTIME_CONSTRUCTION_IDS",
    "ConstructionRegistryError",
    "DuplicateConstructionError",
    "UnknownConstructionError",
    "ConstructionDefinitionError",
    "ConstructionBuildError",
    "ConstructionValidationError",
    "SlotBuilder",
    "SlotValidator",
    "ConstructionDefinition",
    "ConstructionRegistry",
    "DEFAULT_CONSTRUCTION_REGISTRY",
]

CANONICAL_CONSTRUCTION_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Advisory list from the runtime docs. The registry instance remains the
# actual source of truth for what is available at runtime.
KNOWN_RUNTIME_CONSTRUCTION_IDS = frozenset(
    {
        "bio_lead_identity",
        "coordination_clauses",
        "copula_attributive_adj",
        "copula_attributive_np",
        "copula_equative_classification",
        "copula_equative_simple",
        "copula_existential",
        "copula_locative",
        "ditransitive_event",
        "intransitive_event",
        "passive_event",
        "possession_existential",
        "possession_have",
        "relative_clause_object_gap",
        "relative_clause_subject_gap",
        "topic_comment_copular",
        "topic_comment_eventive",
        "transitive_event",
    }
)


class ConstructionRegistryError(RuntimeError):
    """Base error for construction-registry failures."""


class DuplicateConstructionError(ConstructionRegistryError):
    """Raised when a construction ID or alias is registered twice."""


class UnknownConstructionError(ConstructionRegistryError):
    """Raised when code asks for a construction that is not registered."""


class ConstructionDefinitionError(ConstructionRegistryError):
    """Raised when a registry entry is malformed."""


class ConstructionBuildError(ConstructionRegistryError):
    """Raised when a slot builder cannot be resolved or executed."""


class ConstructionValidationError(ConstructionRegistryError):
    """Raised when a slot map is invalid for the selected construction."""


class SlotBuilder(Protocol):
    """
    Builder protocol for construction-specific slot maps.

    The authoritative contract is intentionally minimal and matches the
    migration docs: a builder accepts a normalized frame and returns a
    JSON-serializable mapping for one selected construction.
    """

    def __call__(
        self,
        frame: Mapping[str, Any] | Any,
        *,
        lang_code: str,
        topic_entity_id: str | None = None,
        focus_role: str | None = None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        ...


class SlotValidator(Protocol):
    """Optional validation hook for a completed slot map."""

    def __call__(self, slot_map: Mapping[str, Any]) -> None:
        ...


def _normalize_construction_id(value: str) -> str:
    if not isinstance(value, str):
        raise ConstructionDefinitionError(
            f"construction_id must be a string, got {type(value).__name__}"
        )

    normalized = value.strip().lower()
    if not normalized:
        raise ConstructionDefinitionError("construction_id must not be empty")

    if not CANONICAL_CONSTRUCTION_ID_RE.fullmatch(normalized):
        raise ConstructionDefinitionError(
            "construction_id must use canonical snake_case runtime form; "
            f"got {value!r}"
        )

    return normalized


def _normalize_id_set(values: Iterable[str] | None) -> frozenset[str]:
    if values is None:
        return frozenset()

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _normalize_construction_id(value)
        if item not in seen:
            seen.add(item)
            normalized.append(item)

    return frozenset(normalized)


def _normalize_name_tuple(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ConstructionDefinitionError(
                f"slot names must be strings, got {type(value).__name__}"
            )
        item = value.strip()
        if not item:
            raise ConstructionDefinitionError("slot names must not be empty")
        if item not in seen:
            seen.add(item)
            normalized.append(item)
    return tuple(normalized)


def _normalize_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _resolve_dotted_object(path: str) -> object:
    """
    Resolve either ``package.module:attribute`` or ``package.module.attribute``.

    ``:`` is preferred because it cleanly separates the import path from the
    attribute path, but the dotted fallback keeps call sites ergonomic.
    """
    if not isinstance(path, str) or not path.strip():
        raise ConstructionBuildError("slot_builder import path must be a non-empty string")

    raw = path.strip()

    if ":" in raw:
        module_name, attribute_path = raw.split(":", 1)
    else:
        module_name, dot, attribute_path = raw.rpartition(".")
        if not dot:
            raise ConstructionBuildError(
                "slot_builder import path must use 'package.module:callable' "
                f"or 'package.module.callable'; got {path!r}"
            )

    if not module_name or not attribute_path:
        raise ConstructionBuildError(f"invalid slot_builder import path: {path!r}")

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover
        raise ConstructionBuildError(
            f"could not import slot_builder module {module_name!r}"
        ) from exc

    obj: object = module
    try:
        for part in attribute_path.split("."):
            obj = getattr(obj, part)
    except AttributeError as exc:
        raise ConstructionBuildError(
            f"module {module_name!r} does not expose {attribute_path!r}"
        ) from exc

    return obj


@dataclass(frozen=True, slots=True)
class ConstructionDefinition:
    """
    Immutable metadata for one registered runtime construction.

    Notes
    -----
    - ``construction_id`` is the canonical runtime ID used by planner output,
      construction plans, and renderer dispatch.
    - ``slot_builder`` may be a callable or a dotted import path that resolves
      lazily when the builder is first needed.
    - ``wrapper_for`` declares which base constructions a wrapper is allowed
      to package.
    """

    construction_id: str
    slot_builder: SlotBuilder | str | None = None
    description: str | None = None
    aliases: frozenset[str] = field(default_factory=frozenset)
    wrapper_for: frozenset[str] = field(default_factory=frozenset)
    required_slots: tuple[str, ...] = field(default_factory=tuple)
    optional_slots: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: frozenset[str] = field(default_factory=frozenset)
    validator: SlotValidator | None = None

    def __post_init__(self) -> None:
        construction_id = _normalize_construction_id(self.construction_id)
        aliases = _normalize_id_set(self.aliases)
        wrapper_for = _normalize_id_set(self.wrapper_for)
        required_slots = _normalize_name_tuple(self.required_slots)
        optional_slots = _normalize_name_tuple(self.optional_slots)
        metadata = _normalize_metadata(self.metadata)
        tags = frozenset(
            tag.strip().lower()
            for tag in self.tags
            if isinstance(tag, str) and tag.strip()
        )

        if construction_id in aliases:
            raise ConstructionDefinitionError(
                f"construction {construction_id!r} cannot alias itself"
            )

        if construction_id in wrapper_for:
            raise ConstructionDefinitionError(
                f"construction {construction_id!r} cannot wrap itself"
            )

        overlap = set(required_slots) & set(optional_slots)
        if overlap:
            raise ConstructionDefinitionError(
                f"required_slots and optional_slots overlap: {sorted(overlap)!r}"
            )

        if self.slot_builder is not None:
            if isinstance(self.slot_builder, str):
                if not self.slot_builder.strip():
                    raise ConstructionDefinitionError(
                        f"slot_builder path for {construction_id!r} must not be empty"
                    )
            elif not callable(self.slot_builder):
                raise ConstructionDefinitionError(
                    "slot_builder must be a callable, dotted import path, or None; "
                    f"got {type(self.slot_builder).__name__}"
                )

        if self.validator is not None and not callable(self.validator):
            raise ConstructionDefinitionError(
                f"validator for {construction_id!r} must be callable"
            )

        object.__setattr__(self, "construction_id", construction_id)
        object.__setattr__(self, "aliases", aliases)
        object.__setattr__(self, "wrapper_for", wrapper_for)
        object.__setattr__(self, "required_slots", required_slots)
        object.__setattr__(self, "optional_slots", optional_slots)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "tags", tags)

    @property
    def is_wrapper(self) -> bool:
        return bool(self.wrapper_for)

    @property
    def slot_builder_id(self) -> str | None:
        builder = self.slot_builder
        if builder is None:
            return None
        if isinstance(builder, str):
            return builder.strip()
        module = getattr(builder, "__module__", None) or "<unknown>"
        qualname = getattr(builder, "__qualname__", None) or getattr(
            builder, "__name__", "slot_builder"
        )
        return f"{module}.{qualname}"

    def resolve_slot_builder(self) -> SlotBuilder | None:
        builder = self.slot_builder
        if builder is None:
            return None
        if isinstance(builder, str):
            resolved = _resolve_dotted_object(builder)
            if not callable(resolved):
                raise ConstructionBuildError(
                    f"resolved slot_builder for {self.construction_id!r} is not callable"
                )
            return resolved  # type: ignore[return-value]
        return builder

    def supports_base(self, base_construction_id: str) -> bool:
        if not self.wrapper_for:
            return False
        return _normalize_construction_id(base_construction_id) in self.wrapper_for

    def to_dict(self) -> dict[str, Any]:
        return {
            "construction_id": self.construction_id,
            "slot_builder_id": self.slot_builder_id,
            "description": self.description,
            "aliases": sorted(self.aliases),
            "wrapper_for": sorted(self.wrapper_for),
            "required_slots": list(self.required_slots),
            "optional_slots": list(self.optional_slots),
            "metadata": dict(self.metadata),
            "tags": sorted(self.tags),
        }


class ConstructionRegistry:
    """
    Authoritative registry for runtime constructions.

    Responsibilities
    ----------------
    - keep the canonical mapping ``construction_id -> ConstructionDefinition``
    - validate that planner-selected IDs refer to registered constructions
    - optionally resolve slot builders lazily from dotted import paths
    - expose wrapper relationships for discourse packaging and diagnostics
    - build and validate slot maps without introducing backend-specific logic
    """

    def __init__(
        self,
        definitions: Iterable[ConstructionDefinition | Mapping[str, Any]] | None = None,
    ) -> None:
        self._definitions: dict[str, ConstructionDefinition] = {}
        self._aliases: dict[str, str] = {}

        if definitions:
            self.extend(definitions)

    def __contains__(self, construction_id: object) -> bool:
        if not isinstance(construction_id, str):
            return False
        try:
            self.resolve_id(construction_id)
        except UnknownConstructionError:
            return False
        return True

    def __len__(self) -> int:
        return len(self._definitions)

    def __iter__(self) -> Iterator[str]:
        return iter(self.ids())

    def _coerce_definition(
        self,
        value: ConstructionDefinition | Mapping[str, Any],
    ) -> ConstructionDefinition:
        if isinstance(value, ConstructionDefinition):
            return value
        if isinstance(value, Mapping):
            return ConstructionDefinition(**dict(value))
        raise ConstructionDefinitionError(
            "registry entries must be ConstructionDefinition instances or mappings"
        )

    def add(
        self,
        definition: ConstructionDefinition | Mapping[str, Any],
    ) -> ConstructionDefinition:
        entry = self._coerce_definition(definition)
        canonical_id = entry.construction_id

        if canonical_id in self._definitions:
            raise DuplicateConstructionError(
                f"construction {canonical_id!r} is already registered"
            )

        for alias in entry.aliases:
            current_owner = self._aliases.get(alias)
            if current_owner is not None:
                raise DuplicateConstructionError(
                    f"alias {alias!r} is already used by {current_owner!r}"
                )
            if alias in self._definitions:
                raise DuplicateConstructionError(
                    f"alias {alias!r} conflicts with an existing construction ID"
                )

        self._definitions[canonical_id] = entry
        for alias in entry.aliases:
            self._aliases[alias] = canonical_id
        return entry

    def extend(
        self,
        definitions: Iterable[ConstructionDefinition | Mapping[str, Any]],
    ) -> None:
        for definition in definitions:
            self.add(definition)

    def register(
        self,
        construction_id: str,
        **definition_kwargs: Any,
    ) -> Callable[[SlotBuilder], SlotBuilder]:
        """
        Decorator-based registration for slot builders.

        Example
        -------
        >>> registry = ConstructionRegistry()
        >>> @registry.register(
        ...     "copula_equative_simple",
        ...     required_slots=("subject", "predicate"),
        ... )
        ... def build_slots(frame, *, lang_code, **kwargs):
        ...     return {"subject": {}, "predicate": {}}
        """

        normalized_id = _normalize_construction_id(construction_id)

        def decorator(builder: SlotBuilder) -> SlotBuilder:
            self.add(
                ConstructionDefinition(
                    construction_id=normalized_id,
                    slot_builder=builder,
                    **definition_kwargs,
                )
            )
            return builder

        return decorator

    def clear(self) -> None:
        self._definitions.clear()
        self._aliases.clear()

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))

    def aliases(self) -> dict[str, str]:
        return dict(sorted(self._aliases.items()))

    def definitions(self) -> tuple[ConstructionDefinition, ...]:
        return tuple(self._definitions[key] for key in self.ids())

    def resolve_id(self, construction_id: str) -> str:
        normalized = _normalize_construction_id(construction_id)
        if normalized in self._definitions:
            return normalized

        alias_target = self._aliases.get(normalized)
        if alias_target is not None:
            return alias_target

        raise UnknownConstructionError(f"unknown construction_id {construction_id!r}")

    def has(self, construction_id: str) -> bool:
        try:
            self.resolve_id(construction_id)
        except UnknownConstructionError:
            return False
        return True

    def get(self, construction_id: str) -> ConstructionDefinition | None:
        try:
            resolved = self.resolve_id(construction_id)
        except UnknownConstructionError:
            return None
        return self._definitions[resolved]

    def require(self, construction_id: str) -> ConstructionDefinition:
        return self._definitions[self.resolve_id(construction_id)]

    def require_supported(
        self,
        construction_id: str,
        *,
        base_construction_id: str | None = None,
    ) -> ConstructionDefinition:
        """
        Return a registered definition and optionally validate wrapper use.

        When ``base_construction_id`` is provided, the selected construction is
        treated as a wrapper and must explicitly declare support for that base.
        """
        definition = self.require(construction_id)

        if base_construction_id is None:
            return definition

        base_id = self.resolve_id(base_construction_id)

        if not definition.is_wrapper:
            raise ConstructionValidationError(
                f"{definition.construction_id!r} is not registered as a wrapper"
            )

        if base_id not in definition.wrapper_for:
            raise ConstructionValidationError(
                f"{definition.construction_id!r} does not support base "
                f"construction {base_id!r}"
            )

        return definition

    def can_wrap(self, wrapper_id: str, base_construction_id: str) -> bool:
        try:
            wrapper = self.require(wrapper_id)
            base_id = self.resolve_id(base_construction_id)
        except UnknownConstructionError:
            return False
        return base_id in wrapper.wrapper_for

    def wrappers_for(self, base_construction_id: str) -> tuple[ConstructionDefinition, ...]:
        base_id = self.resolve_id(base_construction_id)
        matches = [
            definition
            for definition in self._definitions.values()
            if base_id in definition.wrapper_for
        ]
        return tuple(sorted(matches, key=lambda item: item.construction_id))

    def resolve_slot_builder(self, construction_id: str) -> SlotBuilder:
        definition = self.require(construction_id)
        builder = definition.resolve_slot_builder()
        if builder is None:
            raise ConstructionBuildError(
                f"construction {definition.construction_id!r} has no slot_builder"
            )
        return builder

    def build_slots(
        self,
        construction_id: str,
        frame: Mapping[str, Any] | Any,
        *,
        lang_code: str,
        topic_entity_id: str | None = None,
        focus_role: str | None = None,
        base_construction_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Build and validate the slot map for one registered construction.

        The registry enforces only construction-generic guarantees:
        - the builder exists,
        - the result is mapping-like,
        - required slots are present,
        - optional custom validation hooks can run.

        It intentionally does not perform backend-specific realization or
        lexical decisions.
        """
        definition = self.require_supported(
            construction_id,
            base_construction_id=base_construction_id,
        )
        builder = definition.resolve_slot_builder()
        if builder is None:
            raise ConstructionBuildError(
                f"construction {definition.construction_id!r} has no slot_builder"
            )

        try:
            raw_slot_map = builder(
                frame,
                lang_code=lang_code,
                topic_entity_id=topic_entity_id,
                focus_role=focus_role,
                **kwargs,
            )
        except ConstructionRegistryError:
            raise
        except Exception as exc:
            raise ConstructionBuildError(
                f"slot_builder for {definition.construction_id!r} raised "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        if not isinstance(raw_slot_map, Mapping):
            raise ConstructionValidationError(
                f"slot_builder for {definition.construction_id!r} must return a mapping, "
                f"got {type(raw_slot_map).__name__}"
            )

        slot_map = dict(raw_slot_map)
        self._validate_slot_map(definition, slot_map)
        return slot_map

    def _validate_slot_map(
        self,
        definition: ConstructionDefinition,
        slot_map: Mapping[str, Any],
    ) -> None:
        missing = [
            slot_name
            for slot_name in definition.required_slots
            if slot_name not in slot_map
        ]
        if missing:
            raise ConstructionValidationError(
                f"slot_map for {definition.construction_id!r} is missing required "
                f"slots: {missing!r}"
            )

        if definition.validator is not None:
            try:
                definition.validator(slot_map)
            except ConstructionRegistryError:
                raise
            except Exception as exc:
                raise ConstructionValidationError(
                    f"validator for {definition.construction_id!r} raised "
                    f"{type(exc).__name__}: {exc}"
                ) from exc

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """
        Return a stable, JSON-friendly view of the registry for debugging/tests.
        """
        return {
            construction_id: self._definitions[construction_id].to_dict()
            for construction_id in self.ids()
        }


DEFAULT_CONSTRUCTION_REGISTRY = ConstructionRegistry()