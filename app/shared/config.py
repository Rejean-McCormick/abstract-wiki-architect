# app/shared/config.py
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

    # --- Messaging (Redis) ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_QUEUE_NAME: str = "architect_tasks"

    @property
    def REDIS_URL(self) -> str:
        # Matches 'redis_broker.py' expectation
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # --- External Services ---
    WIKIDATA_SPARQL_URL: str = "https://query.wikidata.org/sparql"
    WIKIDATA_TIMEOUT: int = 30
    
    # --- Persistence ---
    STORAGE_BACKEND: StorageBackend = StorageBackend.FILESYSTEM
    
    # FILESYSTEM CONFIG
    # Pointing to the project root
    FILESYSTEM_REPO_PATH: str = "/mnt/c/MyCode/AbstractWiki/abstract-wiki-architect"
    
    # S3 Config
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_BUCKET_NAME: str = "abstract-wiki-grammars"

    # --- Worker Configuration ---
    WORKER_CONCURRENCY: int = 2

    # --- Feature Flags ---
    USE_MOCK_GRAMMAR: bool = False 
    GF_LIB_PATH: str = "/mnt/c/MyCode/AbstractWiki/gf-rgl"
    GOOGLE_API_KEY: Optional[str] = None

    @property
    def AW_PGF_PATH(self) -> str:
        """Dynamically builds the path to the PGF binary."""
        # CRITICAL FIX: Smart detection of 'gf' folder to prevent 'gf/gf/Wiki.pgf'
        base = self.FILESYSTEM_REPO_PATH.rstrip("/")
        
        if base.endswith("gf"):
             return os.path.join(base, "Wiki.pgf")
        return os.path.join(base, "gf", "Wiki.pgf")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()