from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from architect_http_api.services.grammar_service import grammar_service
from architect_http_api.gf.language_map import get_iso3_code, get_all_supported_codes

# [CHANGE] Removed prefix here to allow root-level /info
router = APIRouter(tags=["grammar"])

class RefineRequest(BaseModel):
    lang: str           # e.g., "zul", "zu", or "Zulu"
    lang_name: str      # e.g., "Zulu"
    instructions: str = ""  # e.g., "Fix noun classes"

# --- SYSTEM INFO ENDPOINTS (Root Level) ---

@router.get("/info")
def get_system_info():
    """
    Returns information about the running architect instance,
    including the list of supported languages (ISO 639-3 codes).
    """
    # In a real scenario, we might filter this list by checking what's 
    # actually in the PGF, but returning the full map is fine for discovery.
    return {
        "status": "online",
        "version": "2.0.0",
        "supported_languages": get_all_supported_codes()
    }

@router.get("/languages")
def get_languages():
    """Alias for /info to get just languages"""
    return get_all_supported_codes()

# --- GRAMMAR REFINEMENT ENDPOINTS ---

@router.post("/grammar/refine")
async def trigger_refinement(req: RefineRequest, background_tasks: BackgroundTasks):
    """
    Trigger the AI Refiner for a specific language.
    This runs in the background. Check logs or file system for results.
    """
    # 1. Normalize the language code to ISO 639-3 (e.g. 'zu' -> 'zul')
    iso_code = get_iso3_code(req.lang)
    if not iso_code:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown language code: {req.lang}. Please use a supported ISO code or Z-ID."
        )

    # 2. Schedule the task
    background_tasks.add_task(
        grammar_service.refine_language_async, 
        iso_code, 
        req.lang_name, 
        req.instructions
    )

    return {
        "status": "queued",
        "message": f"AI Refinement started for {req.lang_name} ({iso_code}). Check 'gf/contrib/{iso_code}' in ~30s.",
        "target_path": f"gf/contrib/{iso_code}"
    }