from __future__ import annotations

"""
Entry point for the Abstract Wiki Architect HTTP API.

This module creates the FastAPI application, wires up middleware, and mounts
all versioned routers under a common prefix.

Intended usage:
    uvicorn architect_http_api.main:app --host 0.0.0.0 --port 8000
"""

import logging
import os
from typing import List, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from architect_http_api.logging.config import configure_logging
# UPDATE: Added 'grammar' to the router imports
from architect_http_api.routers import ai, entities, frames, generate, grammar
from architect_http_api.gf import language_map


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


# Base prefix for all API endpoints inside this service.
# The external path prefix (/abstract_wiki_architect) is handled by Nginx.
API_PREFIX: str = _env("ARCHITECT_API_PREFIX", "")
API_VERSION: str = _env("ARCHITECT_API_VERSION", "")

# Normalize and build final prefix, e.g. "/api/v1"
RAW_API_ROOT = f"{API_PREFIX.rstrip('/')}/{API_VERSION.lstrip('/')}"
API_ROOT: str = RAW_API_ROOT if RAW_API_ROOT.startswith("/") else f"/{RAW_API_ROOT}"
if API_ROOT == "//" or API_ROOT == "/":
    API_ROOT = ""


def _parse_cors_origins(raw: str) -> List[str]:
    """
    Parse a comma-separated list of origins into a list.
    """
    raw = (raw or "").strip()
    if not raw or raw == "*":
        return ["*"]

    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.
    """
    configure_logging()
    logger = logging.getLogger("architect_http_api")

    version = _env("ARCHITECT_HTTP_API_VERSION", "0.1.0")
    docs_enabled = _env("ARCHITECT_HTTP_API_ENABLE_DOCS", "true").lower() == "true"

    app = FastAPI(
        title="Abstract Wiki Architect HTTP API",
        version=version,
        openapi_url="/openapi.json" if docs_enabled else None,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
    )

    # CORS configuration
    cors_origins = _parse_cors_origins(
        _env("ARCHITECT_HTTP_API_CORS_ORIGINS", "*")
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def _on_startup() -> None:  # noqa: D401
        """
        Initialize process-wide resources on startup.
        """
        logger.info(
            "Starting Abstract Wiki Architect HTTP API",
            extra={
                "version": version,
                "api_root": API_ROOT,
                "cors_origins": cors_origins,
            },
        )

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:  # noqa: D401
        """
        Clean up resources on shutdown.
        """
        logger.info("Shutting down Abstract Wiki Architect HTTP API")

    # Simple health check
    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {
            "status": "ok",
            "version": version,
            "api_root": API_ROOT,
        }

    # --- Language List Endpoint ---
    # Used by frontend to populate the 300+ language selector
    @app.get("/languages", tags=["system"])
    async def get_supported_languages() -> List[Dict[str, str]]:
        """
        Returns a list of all supported languages (RGL + Factory).
        Format: [{"code": "eng", "name": "English", "z_id": "Z1002"}]
        """
        codes = language_map.get_all_supported_codes()
        results = []
        for code in codes:
            z_id = language_map.get_z_language(code)
            # Basic capitalization for name (e.g. 'zul' -> 'Zulu')
            # In a real app, you might map this to a localized display name
            name = code.capitalize() 
            results.append({
                "code": code,
                "name": name,
                "z_id": z_id or ""
            })
        # Sort alphabetically by code
        return sorted(results, key=lambda x: x["code"])

    # Mount versioned routers under /api/v1/...
    app.include_router(generate.router, prefix=API_ROOT)
    app.include_router(entities.router, prefix=API_ROOT)
    app.include_router(frames.router, prefix=API_ROOT)
    app.include_router(ai.router, prefix=API_ROOT)
    
    # UPDATE: Mount the grammar refinement router
    # This exposes endpoints like /grammar/refine
    app.include_router(grammar.router, prefix=API_ROOT)

    return app


# Default application instance
app = create_app()


# ---------------------------------------------------------------------------
# Local development entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    host = _env("ARCHITECT_HTTP_API_HOST", "0.0.0.0")
    port_str = _env("ARCHITECT_HTTP_API_PORT", "8000")

    try:
        port = int(port_str)
    except ValueError:
        raise SystemExit(
            f"Invalid ARCHITECT_HTTP_API_PORT value {port_str!r}; must be an integer."
        ) from None

    import uvicorn

    uvicorn.run(
        "architect_http_api.main:app",
        host=host,
        port=port,
        reload=_env("ARCHITECT_HTTP_API_RELOAD", "false").lower() == "true",
    )