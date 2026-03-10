# app/shared/config.py
from __future__ import annotations

import os
import sys
from enum import Enum
from pathlib import Path
from typing import ClassVar, Optional

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOTENV_PATH = _PROJECT_ROOT / ".env"
_PGF_FILENAME = "semantik_architect.pgf"


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

    Important PGF-path behavior:
    - Prefer explicit PGF_PATH.
    - Accept deprecated AW_PGF_PATH as fallback.
    - Default only to <repo>/gf/semantik_architect.pgf.
    - Never infer the compiled PGF from GF_LIB_PATH / gf-rgl.
    """

    _PROJECT_ROOT: ClassVar[Path] = _PROJECT_ROOT
    _DOTENV_PATH: ClassVar[Path] = _DOTENV_PATH

    # --- Application Meta ---
    APP_NAME: str = "Semantik Architect"

    # Accept both APP_ENV and legacy ENV from env files.
    APP_ENV: AppEnv = Field(
        default=AppEnv.DEVELOPMENT,
        validation_alias=AliasChoices("APP_ENV", "ENV"),
    )

    @property
    def ENV(self) -> str:
        """Alias for APP_ENV to support legacy calls (settings.ENV)."""
        return self.APP_ENV.value

    DEBUG: bool = True

    # --- HTTP Routing / Deployment Topology ---
    ARCHITECT_BASE_PATH: str = Field(
        default="/semantik_architect",
        description="Public UI base path (Next.js basePath).",
    )

    ARCHITECT_API_ROOT_PATH: str = Field(
        default="",
        description="Public mount prefix for the API when behind a reverse proxy. Empty for local dev.",
    )

    API_V1_PREFIX: str = Field(
        default="/api/v1",
        description="Canonical API prefix (versioned).",
    )

    # --- Security ---
    API_SECRET: Optional[str] = None
    API_KEY: Optional[str] = None  # Back-compat alias

    # --- Logging & Observability ---
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    OTEL_SERVICE_NAME: str = "architect-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None

    # --- Messaging & State (Redis) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_QUEUE_NAME: str = "architect_tasks"
    SESSION_TTL_SEC: int = 600

    # --- External Services ---
    WIKIDATA_SPARQL_URL: str = "https://query.wikidata.org/sparql"
    WIKIDATA_TIMEOUT: int = 30

    # --- AI & DevOps ---
    GEMINI_API_KEY: str = ""
    GOOGLE_API_KEY: Optional[str] = None  # Deprecated alias for Gemini
    AI_MODEL_NAME: str = "gemini-1.5-pro"

    # GitHub Integration
    GITHUB_TOKEN: Optional[str] = None
    REPO_URL: str = "https://github.com/your-org/semantik-architect"

    # --- Persistence ---
    STORAGE_BACKEND: StorageBackend = StorageBackend.FILESYSTEM

    # FILESYSTEM CONFIG
    FILESYSTEM_REPO_PATH: str = str(_PROJECT_ROOT)

    # S3 Config
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_BUCKET_NAME: str = "abstract-wiki-grammars"

    # --- Worker Configuration ---
    WORKER_CONCURRENCY: int = 2

    # --- Feature Flags ---
    USE_MOCK_GRAMMAR: bool = False

    # Path to vendored GF/RGL sources/libs; this is NOT the compiled PGF artifact.
    GF_LIB_PATH: str = "/usr/local/lib/gf"

    # --- Grammar Binary Path (PGF) ---
    PGF_PATH: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("PGF_PATH"),
        description="Path to semantik_architect.pgf. Prefer PGF_PATH; AW_PGF_PATH is deprecated.",
    )
    AW_PGF_PATH: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AW_PGF_PATH"),
        description="Deprecated alias for PGF_PATH. Prefer PGF_PATH.",
    )

    # --- Dynamic Path Resolution ---
    @property
    def REPO_ROOT(self) -> str:
        return self.FILESYSTEM_REPO_PATH

    @property
    def ROOT_DIR(self) -> str:
        return self.FILESYSTEM_REPO_PATH

    @property
    def PROJECT_ROOT(self) -> str:
        return self.FILESYSTEM_REPO_PATH

    @property
    def TOPOLOGY_WEIGHTS_PATH(self) -> str:
        return str(Path(self.FILESYSTEM_REPO_PATH) / "data" / "config" / "topology_weights.json")

    @property
    def GOLD_STANDARD_PATH(self) -> str:
        return str(Path(self.FILESYSTEM_REPO_PATH) / "data" / "tests" / "gold_standard.json")

    @staticmethod
    def _normalize_pgf_path(value: str) -> str:
        value = (value or "").strip()
        if not value:
            return value

        p = Path(value)
        if value.endswith(("/", "\\")) or p.suffix.lower() != ".pgf":
            p = p / _PGF_FILENAME

        return str(p)

    @staticmethod
    def _normalize_url_path(value: str, *, allow_empty: bool = True) -> str:
        s = (value or "").strip()
        if not s or s == "/":
            return "" if allow_empty else "/"
        if not s.startswith("/"):
            s = "/" + s
        return s.rstrip("/")

    @staticmethod
    def _join_url_paths(*parts: str) -> str:
        cleaned = []
        for p in parts:
            if p is None:
                continue
            s = str(p).strip()
            if not s:
                continue
            cleaned.append(s.strip("/"))
        if not cleaned:
            return ""
        return "/" + "/".join(cleaned)

    @staticmethod
    def _coerce_repo_root(value: str) -> Path:
        """
        Normalize repo root and guard against a common misconfiguration where a
        grammar subdir (gf/ or gf-rgl/) is accidentally supplied as the repo root.
        """
        raw = (value or "").strip()
        p = Path(raw).expanduser() if raw else _PROJECT_ROOT

        if not p.is_absolute():
            p = (_PROJECT_ROOT / p).resolve()
        else:
            p = p.resolve()

        if p.name in {"gf", "gf-rgl"} and p.parent.exists():
            return p.parent

        return p

    def _abspath_from_repo(self, value: str) -> str:
        p = Path(value).expanduser()
        if not p.is_absolute():
            p = (Path(self.FILESYSTEM_REPO_PATH) / p).resolve()
        else:
            p = p.resolve()
        return str(p)

    @property
    def PUBLIC_API_V1_PATH(self) -> str:
        """
        Public-facing /api/v1 path as seen by clients.
        Examples:
          - local dev:              /api/v1
          - behind base path:       /semantik_architect/api/v1
        """
        return self._join_url_paths(self.ARCHITECT_API_ROOT_PATH, self.API_V1_PREFIX)

    @model_validator(mode="after")
    def _configure_security_and_test_defaults(self) -> "Settings":
        # Sync alias fields
        if self.API_SECRET and not self.API_KEY:
            self.API_KEY = self.API_SECRET
        elif self.API_KEY and not self.API_SECRET:
            self.API_SECRET = self.API_KEY

        # Under pytest, enforce deterministic auth unless explicitly provided.
        is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules)
        if is_pytest:
            self.APP_ENV = AppEnv.TESTING
            if not self.API_SECRET and not self.API_KEY:
                self.API_KEY = "test-api-key"
                self.API_SECRET = self.API_KEY

        return self

    @model_validator(mode="after")
    def _normalize_http_paths(self) -> "Settings":
        self.ARCHITECT_BASE_PATH = (
            self._normalize_url_path(self.ARCHITECT_BASE_PATH, allow_empty=False)
            or "/semantik_architect"
        )
        self.ARCHITECT_API_ROOT_PATH = self._normalize_url_path(
            self.ARCHITECT_API_ROOT_PATH,
            allow_empty=True,
        )
        self.API_V1_PREFIX = (
            self._normalize_url_path(self.API_V1_PREFIX, allow_empty=False)
            or "/api/v1"
        )
        return self

    @model_validator(mode="after")
    def _normalize_repo_paths(self) -> "Settings":
        repo_root = self._coerce_repo_root(self.FILESYSTEM_REPO_PATH)
        self.FILESYSTEM_REPO_PATH = str(repo_root)

        gf_lib = (self.GF_LIB_PATH or "").strip()
        if gf_lib:
            self.GF_LIB_PATH = self._abspath_from_repo(gf_lib)

        return self

    @model_validator(mode="after")
    def _resolve_pgf_path(self) -> "Settings":
        """
        Resolve the compiled PGF path deterministically.

        Precedence:
          1) PGF_PATH
          2) AW_PGF_PATH (deprecated)
          3) <repo_root>/gf/semantik_architect.pgf

        Deliberately does NOT use GF_LIB_PATH / gf-rgl as a PGF fallback.
        """
        explicit = (self.PGF_PATH or "").strip()
        legacy = (self.AW_PGF_PATH or "").strip()

        if explicit:
            self.PGF_PATH = self._abspath_from_repo(self._normalize_pgf_path(explicit))
            return self

        if legacy:
            self.PGF_PATH = self._abspath_from_repo(self._normalize_pgf_path(legacy))
            return self

        self.PGF_PATH = str(Path(self.FILESYSTEM_REPO_PATH) / "gf" / _PGF_FILENAME)
        return self

    model_config = SettingsConfigDict(
        env_file=str(_DOTENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()