# app\adapters\api\main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.shared.container import container
from app.shared.config import settings

# Import Routers
# Note: We import the modules directly to ensure 'container.wire' works correctly
from app.adapters.api.routers import generation, management, health

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application lifecycle.
    1. Startup: Wires DI container, connects to infrastructure.
    2. Shutdown: Closes connections.
    """
    logger.info("app_startup", env=settings.ENV)

    # 1. Wire the Container
    # We must explicitly tell the container which modules use the @inject decorator.
    container.wire(modules=[
        "app.adapters.api.routers.generation",
        "app.adapters.api.routers.management",
        "app.adapters.api.routers.health",
        "app.adapters.api.dependencies"
    ])

    # 2. Infrastructure Initialization
    # Although dependencies are lazy, we explicitly connect to the broker 
    # to catch configuration errors early (Fail Fast).
    broker = container.message_broker()
    try:
        await broker.connect()
        logger.info("broker_connected")
    except Exception as e:
        logger.error("broker_connection_failed", error=str(e))
        # Depending on policy, we might raise e here to abort startup
    
    yield
    
    # 3. Shutdown / Cleanup
    logger.info("app_shutdown")
    await broker.disconnect()

def create_app() -> FastAPI:
    """Factory function to create the FastAPI application."""
    
    app = FastAPI(
        title=settings.APP_NAME,
        version="2.0.0",
        description="Abstract Wiki Core Engine (Hexagonal Architecture)",
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
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
    app.include_router(health.router)
    app.include_router(generation.router)
    app.include_router(management.router)

    return app

# Entry point for local debugging (e.g. `python app/adapters/api/main.py`)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.adapters.api.main:create_app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True, 
        factory=True
    )