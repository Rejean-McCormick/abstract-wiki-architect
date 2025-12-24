# app/api/routes.py
import structlog
from fastapi import APIRouter, HTTPException, Path, Body, Depends
from typing import Dict, Any

from app.adapters.ninai import ninai_adapter
from app.adapters.engines.gf_wrapper import gf_wrapper
from app.shared.config import settings

# Logger setup
logger = structlog.get_logger()

# Router definition
router = APIRouter(prefix="/api/v1", tags=["Generation"])

@router.post("/generate/{lang_code}")
async def generate_text(
    lang_code: str = Path(..., min_length=3, max_length=3, description="ISO 639-3 Code (e.g., 'eng', 'fra')"),
    payload: Dict[str, Any] = Body(..., description="Ninai JSON Recursive Statement")
):
    """
    **v2.1 Generation Endpoint**
    
    Orchestrates the 'Ninai -> Lexicon -> GF' pipeline.
    
    - **Step 1:** Adapter validates JSON and grounds entities using Zone B Lexicon (Q42 -> douglas_adams_PN).
    - **Step 2:** GF Engine linearizes the grounded frame into surface text.
    """
    
    # 1. Telemetry Context
    log = logger.bind(lang=lang_code, endpoint="generate")
    log.info("generation_request_received")

    try:
        # --- PHASE 1: ADAPT & GROUND ---
        # Converts { "function": "mkBio", "args": ["Q42"] } 
        # into BioFrame(subject="Douglas Adams", meta={"subject_gf": "douglas_adams_PN"})
        # The 'target_lang' ensures we fetch the correct translation for the QID (v2.1 Requirement).
        domain_frame = ninai_adapter.parse(payload, target_lang=lang_code)
        
        # --- PHASE 2: LINEARIZE (GF ENGINE) ---
        # The C-Runtime uses the 'meta' fields to pick the specific RGL function
        # Await is critical here as linearization might involve thread-pool execution
        output_text = await gf_wrapper.linearize(lang_code, domain_frame)
        
        # --- PHASE 3: RESPONSE ---
        return {
            "status": "success",
            "lang": lang_code,
            "text": output_text,
            "meta": {
                "grounding": domain_frame.meta,
                "context_id": domain_frame.context_id
            }
        }

    except ValueError as e:
        # Mapped per Ledger: 422 for Validation/Lexicon Errors (e.g. malformed Ninai JSON)
        log.warning("validation_error", error=str(e))
        raise HTTPException(status_code=422, detail=str(e))

    except KeyError as e:
        # Mapped per Ledger: 404 for Language Not Found in PGF
        log.error("language_missing", error=str(e))
        raise HTTPException(status_code=404, detail=f"Language '{lang_code}' not loaded in Runtime.")

    except Exception as e:
        # Mapped per Ledger: 500 for C-Runtime Crashes or unexpected failures
        log.error("critical_runtime_failure", error=str(e))
        raise HTTPException(status_code=500, detail="GF Runtime Failure")