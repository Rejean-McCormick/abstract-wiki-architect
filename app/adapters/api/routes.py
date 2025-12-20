# app/adapters/api/routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from typing import List, Optional

from app.core.domain.models import Language, SemanticFrame
from app.core.use_cases.generate_text import GenerateText
from app.core.use_cases.build_language import BuildLanguage
from app.core.use_cases.onboard_language_saga import OnboardLanguageSaga
from app.adapters.api.dependencies import (
    verify_api_key,
    get_generate_text_use_case,
    get_build_language_use_case,
    get_onboard_saga
)
from app.shared.telemetry import get_tracer

router = APIRouter()
tracer = get_tracer(__name__)

# --- Request/Response Models ---

class GenerationRequest(BaseModel):
    language_code: str
    frame: SemanticFrame

class CompilationRequest(BaseModel):
    language_code: str
    # Optional: Force re-compilation even if cache exists
    force: bool = False

# --- Endpoints ---

@router.post(
    "/generate",
    summary="Generate Natural Language",
    description="Converts a Semantic Frame into human-readable text using the GF Engine.",
    response_model=dict
)
async def generate_text(
    request: GenerationRequest,
    # Security: Generation might be public or protected depending on business logic.
    # For v1.0, we keep it protected to prevent abuse.
    _auth: str = Depends(verify_api_key),
    use_case: GenerateText = Depends(get_generate_text_use_case)
):
    with tracer.start_as_current_span("api_generate_text") as span:
        span.set_attribute("gen.language", request.language_code)
        
        try:
            result = await use_case.execute(request.language_code, request.frame)
            return {"status": "success", "text": result}
        except Exception as e:
            # Domain exceptions should be caught and mapped to HTTP codes here
            span.record_exception(e)
            raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/compile",
    summary="Trigger Grammar Compilation",
    description="Queues a CPU-intensive job to compile GF source files into PGF.",
    status_code=status.HTTP_202_ACCEPTED
)
async def trigger_compilation(
    request: CompilationRequest,
    # Security: STRICTLY PROTECTED. This burns CPU cycles.
    _auth: str = Depends(verify_api_key),
    use_case: BuildLanguage = Depends(get_build_language_use_case)
):
    with tracer.start_as_current_span("api_trigger_compile") as span:
        span.set_attribute("compile.language", request.language_code)
        
        try:
            # The use case now returns a Job ID or status
            job_id = await use_case.execute(request.language_code)
            return {"status": "queued", "job_id": job_id, "language": request.language_code}
        except Exception as e:
            span.record_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to queue compilation: {str(e)}")

@router.post(
    "/onboard",
    summary="Onboard New Language",
    description="Saga: Scaffolds directories, fetches external data, and triggers initial build.",
    status_code=status.HTTP_201_CREATED
)
async def onboard_language(
    language: Language,
    _auth: str = Depends(verify_api_key),
    saga: OnboardLanguageSaga = Depends(get_onboard_saga)
):
    with tracer.start_as_current_span("api_onboard_language") as span:
        span.set_attribute("onboard.iso_code", language.iso_code)
        
        try:
            await saga.execute(language)
            return {"status": "onboarded", "language": language.name}
        except Exception as e:
            span.record_exception(e)
            raise HTTPException(status_code=400, detail=str(e))

@router.get("/health")
async def health_check():
    """
    K8s Liveness Probe.
    """
    return {"status": "ok", "version": "1.0.0"}