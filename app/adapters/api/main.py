# app/adapters/api/main.py
import uvicorn
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.shared.container import container
from app.shared.config import settings

# Import Routers
# Note: We import the modules directly to ensure 'container.wire' works correctly
from app.adapters.api.routers import (
    generation, 
    management, 
    health, 
    tools, 
    languages,
    # entities,  # [OPTIONAL] Uncomment if you have created these files
    # frames     # [OPTIONAL] Uncomment if you have created these files
)

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application lifecycle.
    1. Startup: Wires DI container, connects to infrastructure.
    2. Shutdown: Closes connections.
    """
    # FIX: Use APP_ENV per v2.0 Ledger
    env_name = getattr(settings, "APP_ENV", "development")
    logger.info("app_startup", env=env_name)

    # 1. Wire the Container
    # We must explicitly tell the container which modules use the @inject decorator.
    container.wire(modules=[
        "app.adapters.api.routers.generation",
        "app.adapters.api.routers.management",
        "app.adapters.api.routers.health",
        "app.adapters.api.routers.tools",
        "app.adapters.api.routers.languages",
        # "app.adapters.api.routers.entities", # [OPTIONAL]
        # "app.adapters.api.routers.frames",   # [OPTIONAL]
        "app.adapters.api.dependencies"
    ])

    # 2. Infrastructure Initialization
    # Although dependencies are lazy, we explicitly connect to the broker 
    # to catch configuration errors early (Fail Fast).
    
    # Message Broker
    broker = container.message_broker()
    try:
        await broker.connect()
        logger.info("broker_connected")
    except Exception as e:
        logger.error("broker_connection_failed", error=str(e))
        # Depending on policy, we might raise e here to abort startup
    
    # Task Queue (ARQ) -- [ADDED]
    task_queue = container.task_queue()
    try:
        await task_queue.connect()
        logger.info("task_queue_connected")
    except Exception as e:
        logger.error("task_queue_connection_failed", error=str(e))
    
    yield
    
    # 3. Shutdown / Cleanup
    logger.info("app_shutdown")
    await broker.disconnect()
    await task_queue.disconnect() # -- [ADDED]

def create_app() -> FastAPI:
    """Factory function to create the FastAPI application."""
    
    # Check environment for docs visibility
    is_dev = getattr(settings, "APP_ENV", "development") == "development"
    app_name = getattr(settings, "APP_NAME", "Abstract Wiki Architect")

    app = FastAPI(
        title=app_name,
        version="2.0.0",
        description="Abstract Wiki Core Engine (Hexagonal Architecture)",
        lifespan=lifespan,
        docs_url="/docs" if is_dev else None,
        redoc_url=None
    )

    # Global Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # TODO: Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    # CRITICAL FIX: Mount under /api/v1 to match v2.0 spec and curl commands
    
    # Public Read Endpoints
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(languages.router, prefix="/api/v1/languages", tags=["Languages"])
    
    # [OPTIONAL] Uncomment if you have created these files
    # app.include_router(entities.router, prefix="/api/v1/entities", tags=["Entities"]) 
    # app.include_router(frames.router, prefix="/api/v1/frames", tags=["Frames"])       

    # Core Logic
    app.include_router(generation.router, prefix="/api/v1")
    
    # Admin / Management (Protected)
    app.include_router(management.router, prefix="/api/v1")

    # Developer Tools
    app.include_router(tools.router, prefix="/api/v1/tools", tags=["System Tools"])

    return app

def start():
    """
    Entry point for the 'architect-api' CLI script defined in pyproject.toml.
    """
    is_dev = getattr(settings, "APP_ENV", "development") == "development"
    
    uvicorn.run(
        "app.adapters.api.main:create_app", 
        host="0.0.0.0", 
        port=8000, 
        reload=is_dev, 
        factory=True
    )

# Entry point for local debugging (e.g. `python app/adapters/api/main.py`)
if __name__ == "__main__":
    start()