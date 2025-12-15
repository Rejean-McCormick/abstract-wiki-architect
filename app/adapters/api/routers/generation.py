# app\adapters\api\routers\generation.py
from fastapi import APIRouter, Depends, HTTPException, status, Body
import structlog

from app.core.domain.models import Frame, Sentence
from app.core.use_cases.generate_text import GenerateText
from app.core.domain.exceptions import (
    LanguageNotFoundError, 
    InvalidFrameError, 
    UnsupportedFrameTypeError,
    DomainError
)
from app.adapters.api.dependencies import get_generate_text_use_case, verify_api_key

logger = structlog.get_logger()

# We apply the API Key security dependency at the router level
router = APIRouter(
    prefix="/generate", 
    tags=["Generation"],
    dependencies=[Depends(verify_api_key)]
)

@router.post(
    "/{lang_code}", 
    response_model=Sentence,
    status_code=status.HTTP_200_OK,
    summary="Generate Text from Abstract Frame"
)
async def generate_text(
    lang_code: str,
    frame: Frame = Body(..., description="Abstract Semantic Frame payload"),
    use_case: GenerateText = Depends(get_generate_text_use_case)
):
    """
    Converts a Semantic Frame (abstract intent) into a concrete Sentence in the target language.
    
    **Path Parameters:**
    * `lang_code`: ISO 639-3 language code (e.g., 'eng', 'fra', 'zul').
    
    **Body:**
    * `frame`: A JSON object describing the semantic intent. Must include `frame_type`.
    
    **Returns:**
    * A `Sentence` object containing the generated text and debug metadata.
    """
    try:
        # Delegate to the Clean Architecture Use Case
        sentence = await use_case.execute(lang_code, frame)
        return sentence

    except LanguageNotFoundError as e:
        # Map Domain Error -> HTTP 404
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=str(e)
        )
    
    except (InvalidFrameError, UnsupportedFrameTypeError) as e:
        # Map Validation Errors -> HTTP 422
        logger.warning("generation_bad_request", lang=lang_code, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
            detail=str(e)
        )

    except DomainError as e:
        # Catch-all for other expected domain errors -> HTTP 400
        logger.error("generation_domain_error", lang=lang_code, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Generation failed: {str(e)}"
        )
        
    except Exception as e:
        # Unexpected System Errors -> HTTP 500 (Logged by the Use Case or Middleware)
        # We re-raise to let FastAPI's default handler process it, 
        # or customize if we want to hide stack traces.
        logger.critical("unexpected_generation_crash", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during text generation."
        )