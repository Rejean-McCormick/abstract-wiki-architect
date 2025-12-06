"""
architect_http_api
------------------

HTTP API layer for Abstract Wiki Architect.

This package exposes:

- ``create_app()``: application factory returning a FastAPI instance.
- ``app``: a module-level ASGI application (when available), suitable for
  uvicorn / gunicorn entrypoints like ``architect_http_api:app``.
"""

from importlib import metadata as _metadata
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # Only imported for type checkers, no runtime dependency.
    from fastapi import FastAPI  # pragma: no cover
else:
    FastAPI = object  # type: ignore[misc, assignment]


# ---------------------------------------------------------------------------
# Package metadata
# ---------------------------------------------------------------------------

try:
    __version__: str = _metadata.version("abstract-wiki-architect")
except _metadata.PackageNotFoundError:  # When running from source tree
    __version__ = "0.0.0"


# ---------------------------------------------------------------------------
# Public application entry points
# ---------------------------------------------------------------------------

# These are populated if architect_http_api.main is present and imports cleanly.
create_app: Optional["FastAPI"]
app: Optional["FastAPI"]

try:
    # main.py is expected to define:
    #   - create_app() -> FastAPI
    #   - app: FastAPI
    from .main import create_app, app  # type: ignore[assignment]
except ImportError:
    # Allow importing the package even before main.py is implemented,
    # or in environments where FastAPI is not yet installed.
    create_app = None  # type: ignore[assignment]
    app = None  # type: ignore[assignment]


__all__ = [
    "__version__",
    "create_app",
    "app",
]
