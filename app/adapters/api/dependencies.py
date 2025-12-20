# app/adapters/api/dependencies.py
import secrets
from typing import Annotated
from fastapi import Depends, Header, HTTPException, status
from dependency_injector.wiring import inject, Provide

from app.shared.container import Container
from app.shared.config import settings

# Import Use Cases for type hinting
# Ensure these paths match your actual core structure
from app.core.use_cases.generate_text import GenerateText
from app.core.use_cases.build_language import BuildLanguage
from app.core.use_cases.onboard_language_saga import OnboardLanguageSaga

# --- Security Dependencies ---

async def verify_api_key(
    x_api_key: Annotated[str, Header(description="Secret Key for API Access")]
) -> str:
    """
    Validates the API Key provided in the request headers.
    
    Hardening (Phase 1):
    - Uses constant-time comparison to prevent timing attacks.
    - Rejects requests immediately if the key is invalid.
    """
    # Verify the secret exists in config
    if not settings.API_SECRET:
        # Fail safe if server is misconfigured
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: API_SECRET not set"
        )

    # Constant-time comparison
    if not secrets.compare_digest(x_api_key, settings.API_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-API-Key credentials"
        )
    
    return x_api_key

# --- Use Case Injection Helpers ---

@inject
def get_generate_text_use_case(
    use_case: GenerateText = Depends(Provide[Container.generate_text_use_case])
) -> GenerateText:
    """Dependency to inject the GenerateText Interactor."""
    return use_case

@inject
def get_build_language_use_case(
    use_case: BuildLanguage = Depends(Provide[Container.build_language_use_case])
) -> BuildLanguage:
    """Dependency to inject the BuildLanguage Interactor."""
    return use_case

@inject
def get_onboard_saga(
    saga: OnboardLanguageSaga = Depends(Provide[Container.onboard_language_saga])
) -> OnboardLanguageSaga:
    """Dependency to inject the OnboardLanguageSaga."""
    return saga