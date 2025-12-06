"""
architect_http_api.services
---------------------------

Service layer aggregation for the Architect HTTP API.

Routers and other callers should import service classes from this package
instead of depending directly on repositories or the underlying NLG engine.

Example:

    from architect_http_api.services import FramesService, GenerationsService
"""

from .nlg_client import NLGClient
from .ai_client import AIClient
from .entities_service import EntitiesService
from .frames_service import FramesService
from .generations_service import GenerationsService

__all__ = [
    "NLGClient",
    "AIClient",
    "EntitiesService",
    "FramesService",
    "GenerationsService",
]
