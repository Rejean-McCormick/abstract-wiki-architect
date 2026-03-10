# app/shared/config.py
import os
import sys
from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


class AppEnv(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class StorageBackend(str, Enum):
    FILESYSTEM = "filesystem"
    S3 = "s3"


class Settings(BaseSettings):
    """
    Central Configuration Registry.
    Strictly typed and validated via Pydantic.
    """

    # --- Application Meta ---
    APP_NAME: str = "Semantik Architect"

    # Alias 'ENV' to 'APP_ENV' so older code finding settings.ENV works
    APP_ENV: AppEnv = AppEnv.DEVELOPMENT

    @property
    def ENV(self) -> str:
        """Alias for APP_ENV to support legacy calls (settings.ENV)."""
        return self.APP_ENV.value

    DEBUG: bool = True

    # --- HTTP Routing / Deployment Topology ---
    # Public UI base path when deployed behind nginx (Next.js basePath).
    # Keep as /semantik_architect by convention, but allow override via env.
    ARCHITECT_BASE_PATH: str = Field(
        default="/semantik_architect",
        description="Public UI base path (Next.js basePath).",
    )

    # FastAPI/Starlette root_path for URL generation (OpenAPI/Swagger).
    # IMPORTANT: default is empty for local dev (no nginx prefix).
    ARCHITECT_API_ROOT_PATH: str = Field(
        default="",
        description="Public mount prefix for the API when behind a reverse proxy. Empty for local dev.",
    )

    # Canonical API prefix (do not include ARCHITECT_API_ROOT_PATH here).
    API_V1_PREFIX: str = Field(
        default="/api/v1",
        description="Canonical API prefix (versioned).",
    )

    # --- Security ---
    # Default to None. This enables the "Dev Bypass" in dependencies.py.
    # If you want security, set API_SECRET in your .env file.
    API_SECRET: Optional[str] = None

    # Back-compat: tests and older code expect settings.API_KEY.
    # Prefer API_SECRET; API_KEY is treated as an alias.
    API_KEY: Optional[str] = None

    # --- Logging & Observability ---
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    OTEL_SERVICE_NAME: str = "architect-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None

    # --- Messaging & State (Redis) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_QUEUE_NAME: str = "architect_tasks"
    SESSION_TTL_SEC: int = 600  # Default 10 minutes

    # --- External Services ---
    WIKIDATA_SPARQL_URL: str = "https://query.wikidata.org/sparql"
    WIKIDATA_TIMEOUT: int = 30

    # --- AI & DevOps (v2.0) ---
    GEMINI_API_KEY: str = ""
    GOOGLE_API_KEY: Optional[str] = None  # Deprecated alias for Gemini
    AI_MODEL_NAME: str = "gemini-1.5-pro"

    # GitHub Integration
    GITHUB_TOKEN: Optional[str] = None
    REPO_URL: str = "https://github.com/your-org/semantik-architect"

    # --- Persistence ---
    STORAGE_BACKEND: StorageBackend = StorageBackend.FILESYSTEM

    # FILESYSTEM CONFIG
    # Derive root from file location (app/shared/config.py -> root is 3 levels up)
    _PROJECT_ROOT: str = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    FILESYSTEM_REPO_PATH: str = _PROJECT_ROOT

    # S3 Config
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_BUCKET_NAME: str = "abstract-wiki-grammars"

    # --- Worker Configuration ---
    WORKER_CONCURRENCY: int = 2

    # --- Feature Flags ---
    USE_MOCK_GRAMMAR: bool = False
    GF_LIB_PATH: str = "/usr/local/lib/gf"

    # --- Grammar Binary Path (PGF) ---
    # Prefer PGF_PATH; accept AW_PGF_PATH as deprecated alias.
    PGF_PATH: Optional[str] = Field(
        default=None,
        description="Path to semantik_architect.pgf. Prefer PGF_PATH; AW_PGF_PATH is deprecated.",
    )
    AW_PGF_PATH: Optional[str] = Field(
        default=None,
        description="Deprecated alias for PGF_PATH. Prefer PGF_PATH.",
    )

    # --- Dynamic Path Resolution ---
    @property
    def TOPOLOGY_WEIGHTS_PATH(self) -> str:
        return os.path.join(
            self.FILESYSTEM_REPO_PATH, "data", "config", "topology_weights.json"
        )

    @property
    def GOLD_STANDARD_PATH(self) -> str:
        return os.path.join(
            self.FILESYSTEM_REPO_PATH, "data", "tests", "gold_standard.json"
        )

    @staticmethod
    def _normalize_pgf_path(value: str) -> str:
        value = (value or "").strip()
        if not value:
            return value

        # If user provides a directory (or anything not ending with .pgf), append filename.
        if value.endswith(("/", "\\")) or not value.lower().endswith(".pgf"):
            return os.path.join(value, "semantik_architect.pgf")

        return value

    @staticmethod
    def _normalize_url_path(value: str, *, allow_empty: bool = True) -> str:
        s = (value or "").strip()
        if not s or s == "/":
            return "" if allow_empty else "/"
        if not s.startswith("/"):
            s = "/" + s
        s = s.rstrip("/")
        return s

    @staticmethod
    def _join_url_paths(*parts: str) -> str:
        cleaned = []
        for p in parts:
            if p is None:
                continue
            p = str(p).strip()
            if not p:
                continue
            cleaned.append(p.strip("/"))
        if not cleaned:
            return ""
        return "/" + "/".join(cleaned)

    @property
    def PUBLIC_API_V1_PATH(self) -> str:
        """
        Public-facing /api/v1 path as seen by clients (may include ARCHITECT_API_ROOT_PATH).
        Example:
          - local dev:                 /api/v1
          - behind nginx base path:    /semantik_architect/api/v1
        """
        return self._join_url_paths(self.ARCHITECT_API_ROOT_PATH, self.API_V1_PREFIX)

    @model_validator(mode="after")
    def _configure_security_and_test_defaults(self) -> "Settings":
        """
        - Keep API_SECRET and API_KEY in sync (API_KEY is an alias).
        - Under pytest, ensure a deterministic key exists so auth is enforced.
        """
        # Sync alias fields
        if self.API_SECRET and not self.API_KEY:
            self.API_KEY = self.API_SECRET
        elif self.API_KEY and not self.API_SECRET:
            self.API_SECRET = self.API_KEY

        # If running under pytest, enforce a default key unless explicitly provided.
        is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules)
        if is_pytest:
            self.APP_ENV = AppEnv.TESTING
            if not self.API_SECRET and not self.API_KEY:
                self.API_KEY = "test-api-key"
                self.API_SECRET = self.API_KEY

        return self

    @model_validator(mode="after")
    def _normalize_http_paths(self) -> "Settings":
        # Normalize basePath/root_path/prefix so downstream string ops are stable.
        self.ARCHITECT_BASE_PATH = self._normalize_url_path(
            self.ARCHITECT_BASE_PATH, allow_empty=False
        ) or "/semantik_architect"

        # root_path is allowed to be empty for local dev.
        self.ARCHITECT_API_ROOT_PATH = self._normalize_url_path(
            self.ARCHITECT_API_ROOT_PATH, allow_empty=True
        )

        # Ensure API prefix is a proper absolute path segment.
        self.API_V1_PREFIX = self._normalize_url_path(self.API_V1_PREFIX, allow_empty=False) or "/api/v1"

        return self

    @model_validator(mode="after")
    def _resolve_pgf_path(self) -> "Settings":
        # 1) Prefer PGF_PATH if set
        if self.PGF_PATH:
            self.PGF_PATH = self._normalize_pgf_path(self.PGF_PATH)
            return self

        # 2) Fall back to deprecated AW_PGF_PATH
        if self.AW_PGF_PATH:
            self.PGF_PATH = self._normalize_pgf_path(self.AW_PGF_PATH)
            return self

        # 3) Compute from repo path
        base = (self.FILESYSTEM_REPO_PATH or "").rstrip("/\\")
        filename = "semantik_architect.pgf"

        if base.endswith(("gf", "gf-rgl")):
            self.PGF_PATH = os.path.join(base, filename)
        else:
            self.PGF_PATH = os.path.join(base, "gf", filename)

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()