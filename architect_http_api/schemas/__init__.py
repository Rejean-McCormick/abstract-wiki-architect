"""
Top-level export module for HTTP API schemas.

This package groups together all Pydantic models used by the
`architect_http_api` service so they can be imported from a single place, e.g.:

    from architect_http_api.schemas import GenerationRequest, GenerationResponse

If you add new schema modules or public models, remember to:
  1. Import them here, and
  2. Add them to `__all__`.
"""

# Import submodules so tooling like `pkgutil.walk_packages` can see them.
from . import common as common  # noqa: F401
from . import generic as generic  # noqa: F401
from . import ai as ai  # noqa: F401
from . import generations as generations  # noqa: F401
from . import entities as entities  # noqa: F401
from . import frames_metadata as frames_metadata  # noqa: F401

# Re-export selected Pydantic models from submodules.
# Adjust these names to whatever actually exists in your codebase.

# Common / generic primitives
from .common import (  # type: ignore[attr-defined]
    ErrorResponse,
    Pagination,
    SortDirection,
)
from .generic import (  # type: ignore[attr-defined]
    IdModel,
    TimestampedModel,
)

# AI / intent / generation related
from .ai import (  # type: ignore[attr-defined]
    IntentKind,
    IntentInput,
    IntentResult,
)
from .generations import (  # type: ignore[attr-defined]
    GenerationRequest,
    GenerationResponse,
    GenerationStatus,
)

# Domain entities
from .entities import (  # type: ignore[attr-defined]
    FrameSummary,
    PageSummary,
    WikiEntity,
)

# Frames / metadata
from .frames_metadata import (  # type: ignore[attr-defined]
    FrameMetadata,
    FrameSource,
)


__all__ = [
    # subpackages
    "common",
    "generic",
    "ai",
    "generations",
    "entities",
    "frames_metadata",

    # Common / generic primitives
    "ErrorResponse",
    "Pagination",
    "SortDirection",
    "IdModel",
    "TimestampedModel",

    # AI / intents / generations
    "IntentKind",
    "IntentInput",
    "IntentResult",
    "GenerationRequest",
    "GenerationResponse",
    "GenerationStatus",

    # Entities
    "FrameSummary",
    "PageSummary",
    "WikiEntity",

    # Frames / metadata
    "FrameMetadata",
    "FrameSource",
]
