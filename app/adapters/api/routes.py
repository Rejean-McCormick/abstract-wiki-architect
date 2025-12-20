# app/adapters/api/routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

# Domain & Use Cases
from app.core.domain.models import Frame
from app.core.use_cases.generate_text import GenerateText
from app.core.use_cases.build_language import BuildLanguage
from app.core.use_cases.onboard_language_saga import OnboardLanguageSaga

# Dependencies
from app.adapters.api.dependencies import (
    verify_api_key,
    get_generate_text_use_case,
    get_build_language_use_case,
    get_onboard_saga
)
from app.shared.observability import get_tracer

router = APIRouter()
tracer = get_tracer(__name__)

# --- Pydantic Schemas (DTOs) ---

class FrameDTO(BaseModel):
    """Schema for the inner 'frame' object in JSON."""
    frame_type: str
    subject: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)

class GenerationRequest(BaseModel):
    language_code: str
    frame: FrameDTO

class OnboardRequest(BaseModel):
    iso_code: str
    english_name: str

class CompilationRequest(BaseModel):
    language_code: str
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
    # Security: Protected by API Key
    _auth: str = Depends(verify_api_key),
    use_case: GenerateText = Depends(get_generate_text_use_case)
):
    with tracer.start_as_current_span("api_generate_text") as span:
        span.set_attribute("gen.language", request.language_code)
        
        try:
            # Convert Pydantic DTO -> Domain Entity
            domain_frame = Frame(
                frame_type=request.frame.frame_type,
                subject=request.frame.subject,
                meta=request.frame.meta
            )

            result = await use_case.execute(request.language_code, domain_frame)
            
            return {
                "status": "success",
                "text": result.text,
                "lang_code": result.lang_code,
                "debug_info": result.debug_info
            }
        except Exception as e:
            span.record_exception(e)
            # Return 400 for bad requests, 500 for server errors
            raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/languages",
    summary="Onboard New Language",
    description="Saga: Scaffolds directories, fetches external data, and triggers initial build.",
    status_code=status.HTTP_202_ACCEPTED
)
async def onboard_language(
    request: OnboardRequest,
    _auth: str = Depends(verify_api_key),
    saga: OnboardLanguageSaga = Depends(get_onboard_saga)
):
    with tracer.start_as_current_span("api_onboard_language") as span:
        span.set_attribute("onboard.iso_code", request.iso_code)
        
        try:
            # Trigger the Background Saga
            task_id = await saga.execute(request.iso_code, request.english_name)
            return {
                "status": "accepted",
                "message": f"Onboarding started for {request.english_name} ({request.iso_code})",
                "task_id": str(task_id)
            }
        except Exception as e:
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
    _auth: str = Depends(verify_api_key),
    use_case: BuildLanguage = Depends(get_build_language_use_case)
):
    with tracer.start_as_current_span("api_trigger_compile") as span:
        span.set_attribute("compile.language", request.language_code)
        
        try:
            job_id = await use_case.execute(request.language_code)
            return {
                "status": "queued",
                "job_id": job_id,
                "language": request.language_code
            }
        except Exception as e:
            span.record_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to queue compilation: {str(e)}")

@router.get("/health")
async def health_check():
    """K8s Liveness Probe."""
    return {"status": "ok", "version": "1.0.0"}