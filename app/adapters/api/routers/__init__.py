# app\adapters\api\routers\__init__.py
"""
API Route Definitions.

This package contains the specific route handlers (controllers) organized by domain area.
- `generation`: Endpoints for text generation (Core Value).
- `languages`: Endpoints for managing language lifecycles (Onboarding, Building).
- `health`: System health checks.
"""

from .generation import router as generation_router
from .languages import router as languages_router
from .health import router as health_router

__all__ = [
    "generation_router",
    "languages_router",
    "health_router",
]