# app/shared/config.py
import os
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
    APP_NAME: str = "Abstract Wiki Architect"

    # Alias 'ENV' to 'APP_ENV' so older code finding settings.ENV works
    APP_ENV: AppEnv = AppEnv.DEVELOPMENT

    @property
    def ENV(self) -> str:
        """Alias for APP_ENV to support legacy calls (settings.ENV)."""
        return self.APP_ENV.value

    DEBUG: bool = True

    # --- Security ---
    # Default to None. This enables the "Dev Bypass" in dependencies.py.
    # If you want security, set API_SECRET in your .env file.
    API_SECRET: Optional[str] = None

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
    REPO_URL: str = "https://github.com/your-org/abstract-wiki-architect"

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
        description="Path to AbstractWiki.pgf. Prefer PGF_PATH; AW_PGF_PATH is deprecated.",
    )
    AW_PGF_PATH: Optional[str] = Field(
        default=None,
        description="Deprecated alias for PGF_PATH. Prefer PGF_PATH.",
    )

    # --- Dynamic Path Resolution ---
    @property
    def TOPOLOGY_WEIGHTS_PATH(self) -> str:
        return os.path.join(self.FILESYSTEM_REPO_PATH, "data", "config", "topology_weights.json")

    @property
    def GOLD_STANDARD_PATH(self) -> str:
        return os.path.join(self.FILESYSTEM_REPO_PATH, "data", "tests", "gold_standard.json")

    @staticmethod
    def _normalize_pgf_path(value: str) -> str:
        value = (value or "").strip()
        if not value:
            return value

        # If user provides a directory (or anything not ending with .pgf), append filename.
        if value.endswith(("/", "\\")) or not value.lower().endswith(".pgf"):
            return os.path.join(value, "AbstractWiki.pgf")

        return value

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
        filename = "AbstractWiki.pgf"

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
