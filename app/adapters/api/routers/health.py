# app\adapters\api\routers\health.py
from fastapi import APIRouter, Depends, status, Response
from dependency_injector.wiring import inject, Provide
from typing import Dict
import structlog

from app.shared.container import Container
from app.core.ports.message_broker import IMessageBroker
from app.core.ports.lexicon_repository import ILexiconRepository
from app.core.ports.grammar_engine import IGrammarEngine

logger = structlog.get_logger()

router = APIRouter(prefix="/health", tags=["System"])

@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """
    K8s Liveness Probe.
    Returns 200 OK if the service is operational.
    """
    return {"status": "ok", "service": "abstract-wiki-api"}

@router.get("/ready", status_code=status.HTTP_200_OK)
@inject
async def readiness_probe(
    response: Response,
    broker: IMessageBroker = Depends(Provide[Container.message_broker]),
    repo: ILexiconRepository = Depends(Provide[Container.lexicon_repository]),
    engine: IGrammarEngine = Depends(Provide[Container.grammar_engine]),
) -> Dict[str, str]:
    """
    K8s Readiness Probe.
    Performs deep checks on dependencies (Redis, Storage, GF Engine).
    Returns 503 Service Unavailable if any critical component is down.
    """
    health_status = {
        "broker": "down",
        "storage": "down",
        "engine": "down"
    }
    
    # 1. Check Message Broker (Redis)
    try:
        if await broker.health_check():
            health_status["broker"] = "up"
    except Exception as e:
        logger.error("health_check_failed", component="broker", error=str(e))

    # 2. Check Storage (FileSystem)
    try:
        if await repo.health_check():
            health_status["storage"] = "up"
    except Exception as e:
        logger.error("health_check_failed", component="storage", error=str(e))

    # 3. Check Grammar Engine (GF Runtime)
    try:
        if await engine.health_check():
            health_status["engine"] = "up"
    except Exception as e:
        logger.error("health_check_failed", component="engine", error=str(e))

    # Determine overall status
    is_healthy = all(status == "up" for status in health_status.values())

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning("readiness_probe_failed", status=health_status)
    
    return health_status