import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum
from typing import Optional

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
    APP_NAME: str = "abstract-wiki-architect"
    APP_ENV: AppEnv = AppEnv.DEVELOPMENT
    DEBUG: bool = False
    
    # --- Security ---
    API_SECRET: str = "change-me-for-production" 
    
    # --- Logging & Observability ---
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    OTEL_SERVICE_NAME: str = "architect-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None 

    # --- Messaging & State (Redis) ---
    # v2.0 Update: Unified URL and Session Context configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_QUEUE_NAME: str = "architect_tasks"
    SESSION_TTL_SEC: int = 600  # Default 10 minutes for Discourse Context

    # --- External Services ---
    WIKIDATA_SPARQL_URL: str = "https://query.wikidata.org/sparql"
    WIKIDATA_TIMEOUT: int = 30
    
    # --- AI & DevOps (v2.0) ---
    # Credentials for The Architect, Surgeon, and Judge agents
    GOOGLE_API_KEY: Optional[str] = None
    AI_MODEL_NAME: str = "gemini-1.5-pro"
    
    # GitHub Integration for The Judge (Auto-Ticketing)
    GITHUB_TOKEN: Optional[str] = None
    REPO_URL: str = "https://github.com/your-org/abstract-wiki-architect"

    # --- Persistence ---
    STORAGE_BACKEND: StorageBackend = StorageBackend.FILESYSTEM
    
    # FILESYSTEM CONFIG
    # Default to Docker path (/app), fallback to local dev path if env var missing
    FILESYSTEM_REPO_PATH: str = "/app"
    
    # S3 Config
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_BUCKET_NAME: str = "abstract-wiki-grammars"

    # --- Worker Configuration ---
    WORKER_CONCURRENCY: int = 2

    # --- Feature Flags ---
    USE_MOCK_GRAMMAR: bool = False 
    GF_LIB_PATH: str = "/usr/local/lib/gf" # Default to Docker/Linux path

    # --- Dynamic Path Resolution ---
    
    @property
    def TOPOLOGY_WEIGHTS_PATH(self) -> str:
        """v2.0: Path to Udiron linearization weights"""
        return os.path.join(self.FILESYSTEM_REPO_PATH, "data", "config", "topology_weights.json")

    @property
    def GOLD_STANDARD_PATH(self) -> str:
        """v2.0: Path to QA test suite"""
        return os.path.join(self.FILESYSTEM_REPO_PATH, "data", "tests", "gold_standard.json")

    @property
    def PGF_PATH(self) -> str:
        """
        Dynamically builds the path to the PGF binary.
        Ensures consistency between Backend and Worker services.
        """
        # CRITICAL FIX: Smart detection of 'gf' folder to prevent 'gf/gf/'
        base = self.FILESYSTEM_REPO_PATH.rstrip("/")
        
        # The filename MUST match what build_orchestrator.py produces
        filename = "AbstractWiki.pgf" 
        
        # If the base path already points inside 'gf', don't append it again
        if base.endswith("gf"):
             return os.path.join(base, filename)
             
        return os.path.join(base, "gf", filename)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()