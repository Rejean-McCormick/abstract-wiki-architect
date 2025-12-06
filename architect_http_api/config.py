

# architect_http_api/config.py

"""
Configuration for the Abstract Wiki Architect HTTP API.

This module centralizes tunable parameters for the FastAPI HTTP layer,
with sensible defaults that can be overridden via environment variables.

Environment variables
=====================

The following environment variables are recognized:

- AW_HTTP_API_HOST
    Host/interface to bind the HTTP server to.
    Default: "0.0.0.0"

- AW_HTTP_API_PORT
    TCP port for the HTTP server.
    Default: 4000

- AW_HTTP_API_ROOT_PATH
    Optional URL prefix when running behind a reverse proxy.
    Example: "/abstract_wiki_architect"
    Default: "" (no prefix)

- AW_HTTP_API_CORS_ORIGINS
    Comma-separated list of allowed CORS origins.
    Example: "http://localhost:3000,https://konnaxion.com"
    Special value "*" means "allow all origins".
    Default: "http://localhost:3000"

- AW_HTTP_API_DEBUG
    If set to "1", "true", "yes" or "on", enables debug mode
    (e.g. FastAPI debug=True).
    Default: false

- AW_HTTP_API_TITLE
    Optional override for the OpenAPI / docs title.
    Default: "Abstract Wiki Architect HTTP API"

Typical usage
=============

    from architect_http_api.config import get_config

    cfg = get_config()
    app = FastAPI(
        title=cfg.title,
        debug=cfg.debug,
        root_path=cfg.root_path,
    )

    # In the CORS middleware setup:
    #   allow_origins=cfg.cors_origins if not cfg.allow_all_cors else ["*"]
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class HTTPAPIConfig:
    """
    Configuration values for the HTTP API layer.
    """

    host: str = "0.0.0.0"
    port: int = 4000
    root_path: str = ""
    title: str = "Abstract Wiki Architect HTTP API"
    debug: bool = False

    # If allow_all_cors is True, cors_origins is ignored and "*" should be used.
    allow_all_cors: bool = False
    cors_origins: List[str] = field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @classmethod
    def from_env(cls) -> "HTTPAPIConfig":
        """
        Build an HTTPAPIConfig instance using environment variables as
        overrides on top of sensible defaults.
        """
        host = os.getenv("AW_HTTP_API_HOST", cls.host)

        # Port
        port_raw = os.getenv("AW_HTTP_API_PORT", "").strip()
        if port_raw:
            try:
                port = int(port_raw)
                if port <= 0 or port > 65535:
                    port = cls.port
            except ValueError:
                port = cls.port
        else:
            port = cls.port

        # Root path
        root_path = os.getenv("AW_HTTP_API_ROOT_PATH", cls.root_path).strip()
        # Normalize root_path: allow "", or ensure it starts with "/" and has no trailing "/"
        if root_path and not root_path.startswith("/"):
            root_path = "/" + root_path
        if root_path.endswith("/") and root_path != "/":
            root_path = root_path.rstrip("/")

        # Title
        title = os.getenv("AW_HTTP_API_TITLE", cls.title).strip() or cls.title

        # Debug flag
        debug_raw = os.getenv("AW_HTTP_API_DEBUG", "").strip().lower()
        debug = debug_raw in {"1", "true", "yes", "on"}

        # CORS
        cors_raw = os.getenv("AW_HTTP_API_CORS_ORIGINS", "").strip()
        allow_all_cors = False
        cors_origins: List[str]

        if cors_raw:
            if cors_raw == "*":
                allow_all_cors = True
                cors_origins = []
            else:
                parts = [p.strip() for p in cors_raw.split(",") if p.strip()]
                cors_origins = parts or cls.cors_origins
        else:
            cors_origins = cls.cors_origins

        return cls(
            host=host,
            port=port,
            root_path=root_path,
            title=title,
            debug=debug,
            allow_all_cors=allow_all_cors,
            cors_origins=cors_origins,
        )


# Singleton configuration instance
_CONFIG: Optional[HTTPAPIConfig] = None


def get_config() -> HTTPAPIConfig:
    """
    Return the global HTTPAPIConfig instance, creating it from
    environment variables on first use.
    """
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = HTTPAPIConfig.from_env()
    return _CONFIG


def set_config(config: HTTPAPIConfig) -> None:
    """
    Replace the global HTTPAPIConfig instance.

    Mainly useful for tests, where you may want to override configuration
    without touching environment variables.
    """
    global _CONFIG
    _CONFIG = config


__all__ = ["HTTPAPIConfig", "get_config", "set_config"]
