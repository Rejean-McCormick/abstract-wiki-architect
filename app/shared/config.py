# app/shared/config.py
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
    Reads from environment variables or .env file.
    """
    
    # --- Application Meta ---
    APP_NAME: str = "abstract-wiki-architect"
    APP_ENV: AppEnv = AppEnv.DEVELOPMENT
    DEBUG: bool = False
    
    # --- Security (Phase 1) ---
    # Critical for locking down the compilation endpoint.
    # In production, this should be a strong random string.
    API_SECRET: str = "change-me-for-production" 
    
    # --- Logging & Observability (Phase 4) ---
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # Options: 'console', 'json'
    
    # OpenTelemetry Configuration
    OTEL_SERVICE_NAME: str = "architect-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None # e.g., "http://jaeger:4317"

    # --- Messaging (Redis) ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_QUEUE_NAME: str = "architect_tasks"

    @property
    def redis_url(self) -> str:
        """Constructs the Redis Connection URL for ARQ and Redis Client."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # --- External Services (Resilience) ---
    WIKIDATA_SPARQL_URL: str = "https://query.wikidata.org/sparql"
    # Time in seconds before the Circuit Breaker considers a call failed
    WIKIDATA_TIMEOUT: int = 30
    
    # --- Persistence (Phase 2) ---
    STORAGE_BACKEND: StorageBackend = StorageBackend.FILESYSTEM
    
    # Filesystem Config
    FILESYSTEM_REPO_PATH: str = "/app/data"
    
    # S3 Config (Optional - Active if STORAGE_BACKEND=s3)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_BUCKET_NAME: str = "abstract-wiki-grammars"

    # --- Worker Configuration ---
    WORKER_CONCURRENCY: int = 2

    # Pydantic Config: Case-insensitive env var matching, ignores extras
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Singleton instance to be imported across the app
settings = Settings()