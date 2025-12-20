# app/main.py
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.config import settings, AppEnv
from app.shared.telemetry import setup_telemetry, instrument_fastapi
from app.adapters.api.routes import router as api_router

# Configure basic logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    if settings.LOG_FORMAT == "console"
    else '{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application Lifecycle Manager.
    Handles startup (Telemetry, DB connections) and shutdown.
    """
    # 1. Initialize OpenTelemetry (Phase 4)
    setup_telemetry(settings.OTEL_SERVICE_NAME)
    
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode...")
    
    # (Optional) Warm up connections here if needed
    # e.g., await redis_pool.ping()
    
    yield
    
    logger.info("Shutting down application...")
    # Cleanup resources if necessary

def create_app() -> FastAPI:
    """
    Factory function to create the FastAPI application.
    """
    app = FastAPI(
        title="Abstract Wiki Architect",
        version="1.0.0",
        description="Distributed Natural Language Generation Platform (Hexagonal/GF)",
        docs_url="/docs" if settings.APP_ENV != AppEnv.PRODUCTION else None,
        redoc_url="/redoc" if settings.APP_ENV != AppEnv.PRODUCTION else None,
        lifespan=lifespan
    )

    # 2. CORS Configuration
    # Allow all in Dev, restrict in Prod
    origins = ["*"] if settings.DEBUG else ["https://your-domain.com"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Auto-Instrument FastAPI for Tracing
    instrument_fastapi(app)

    # 4. Global Exception Handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        Standardizes HTTP errors (including 401/403 Auth failures).
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "code": exc.status_code,
                "message": exc.detail
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Catches unhandled exceptions to prevent crashing and leaking stack traces in Prod.
        """
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "code": 500,
                "message": "Internal Server Error" if not settings.DEBUG else str(exc)
            }
        )

    # 5. Mount Routes
    app.include_router(api_router, prefix="/api/v1")

    return app

# Entry point for Uvicorn
app = create_app()