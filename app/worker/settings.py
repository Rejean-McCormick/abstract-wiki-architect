# app\worker\settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.shared.config import settings as global_settings

class WorkerSettings(BaseSettings):
    """
    Configuration specific to the Worker Service.
    
    These settings control the behavior of the background processing tasks.
    They can be overridden by environment variables prefixed with 'AW_WORKER_'.
    """
    
    # How many concurrent tasks the worker should handle (usually 1 for heavy CPU tasks like GF compilation)
    CONCURRENCY: int = 1
    
    # Maximum time allowed for a build job before it is cancelled (in seconds)
    BUILD_TIMEOUT_SECONDS: int = 300  # 5 minutes
    
    # Frequency to poll for health/shutdown signals (in seconds)
    POLL_INTERVAL: float = 1.0

    model_config = SettingsConfigDict(
        env_prefix="AW_WORKER_",
        env_file=".env",
        extra="ignore"
    )

worker_settings = WorkerSettings()