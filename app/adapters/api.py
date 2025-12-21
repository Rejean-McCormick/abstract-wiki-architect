import logging
from typing import Any, Dict, Optional, Union
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Header, Body, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError

from app.shared.config import settings
from app.core.domain.frame import BioFrame, EventFrame
from app.core.domain.context import SessionContext, DiscourseEntity
from app.adapters.ninai import ninai_adapter
from app.adapters.redis_bus import redis_bus
# Note: Assuming GrammarEngine is available in core.engine
# In a real run, this import must match your engine's location
from app.core.engine import GrammarEngine 

# Setup Logger
logger = logging.getLogger(settings.OTEL_SERVICE_NAME)

# Initialize App & Engine
app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="Abstract Wiki Architect: Hybrid Neuro-Symbolic NLG Engine"
)

# Global Engine Instance (Singleton)
# The engine loads the PGF binary on startup
engine = GrammarEngine(settings.PGF_PATH)

# ==============================================================================
# LIFECYCLE EVENTS
# ==============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 API Startup: Connecting to Redis...")
    await redis_bus.connect()
    
    # Reload engine if PGF changed (Hot-Reload Logic handled by Worker usually, 
    # but good to verify existence here)
    if not engine.is_loaded():
        logger.warning("⚠️ PGF Binary not found. Engine starting in MOCK mode.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 API Shutdown: Closing connections...")
    await redis_bus.close()

# ==============================================================================
# ENDPOINTS
# ==============================================================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "env": settings.APP_ENV,
        "languages": list(engine.languages.keys()) if engine.is_loaded() else []
    }

@app.post("/api/v1/generate")
async def generate_standard(
    frame: Union[BioFrame, EventFrame, Dict[str, Any]], 
    lang: str,
    x_session_id: Optional[str] = Header(None)
):
    """
    Standard Endpoint (Internal JSON).
    Accepts a flat Semantic Frame and returns generated text.
    """
    return await _process_request(frame, lang, x_session_id, is_ninai=False)

@app.post("/api/v1/ninai")
async def generate_ninai(
    payload: Dict[str, Any] = Body(...),
    lang: str = "eng",
    x_session_id: Optional[str] = Header(None)
):
    """
    v2.0 Ninai Protocol Endpoint.
    Accepts a recursive Ninai Object Tree.
    """
    try:
        # Adapter Step: Transform Ninai Tree -> Internal Frame
        internal_frame = ninai_adapter.parse(payload)
        return await _process_request(internal_frame, lang, x_session_id, is_ninai=True)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Ninai Parse Error: {str(e)}")
    except Exception as e:
        logger.error(f"Ninai Endpoint Failure: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# ==============================================================================
# CORE PROCESSING LOGIC (The Hexagon Center)
# ==============================================================================

async def _process_request(
    frame_data: Union[BioFrame, EventFrame, Dict], 
    lang: str, 
    session_id: Optional[str],
    is_ninai: bool
):
    # 1. Session Management (Discourse Context)
    session_ctx = SessionContext(session_id=session_id or str(uuid4()))
    
    if session_id:
        session_ctx = await redis_bus.get_session(session_id)

    # 2. Inject Context into Frame (if it's a Pydantic model)
    if hasattr(frame_data, "context_id"):
        frame_data.context_id = session_ctx.session_id

    # 3. Call The Engine
    # The engine handles the linguistic logic (Syntax, Morphology, Pronominalization)
    # It returns a result object containing the text and metadata.
    try:
        result = engine.generate(frame_data, lang, session_ctx)
    except Exception as e:
        logger.error(f"Engine Generation Error: {e}")
        raise HTTPException(status_code=500, detail=f"Generation Failed: {str(e)}")

    # 4. Update Discourse State (Post-Generation)
    # If the engine successfully mentioned an entity, update the 'current_focus'
    if result.get("focus_entity"):
        # Convert engine's focus dict to DiscourseEntity
        new_focus = DiscourseEntity(**result["focus_entity"])
        session_ctx.update_focus(new_focus)
        await redis_bus.save_session(session_ctx)

    # 5. Construct Response
    response_payload = {
        "text": result["text"],
        "lang": lang,
        "meta": {
            "strategy": result.get("strategy", "UNKNOWN"),
            "protocol": "ninai" if is_ninai else "standard",
            "session_id": session_ctx.session_id
        }
    }

    # 6. UD Export (Content Negotiation)
    # If the result includes UD tags (from Tier 1 RGL), we can expose them.
    if result.get("ud_tags"):
        response_payload["conllu"] = result["ud_tags"]

    return response_payload