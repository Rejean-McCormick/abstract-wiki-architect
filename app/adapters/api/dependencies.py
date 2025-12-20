# app/adapters/api/dependencies.py
import secrets
from typing import Annotated, Optional
from fastapi import Depends, Header, HTTPException, status
from dependency_injector.wiring import inject, Provide

from app.shared.container import Container
from app.shared.config import settings

# Ports & Domain
from app.core.ports.grammar_engine import IGrammarEngine
from app.core.ports.llm_port import ILanguageModel

# Adapters
from app.adapters.llm_adapter import GeminiAdapter
from app.adapters.engines.gf_wrapper import GFGrammarEngine

# Use Cases
from app.core.use_cases.generate_text import GenerateText
from app.core.use_cases.build_language import BuildLanguage
from app.core.use_cases.onboard_language_saga import OnboardLanguageSaga

# --- Singletons ---
# We instantiate the heavy GF engine once and reuse it across requests.
_grammar_engine_instance = GFGrammarEngine()

def get_grammar_engine() -> IGrammarEngine:
    return _grammar_engine_instance

# --- Security Dependencies ---

async def verify_api_key(
    x_api_key: Annotated[str, Header(description="Secret Key for API Access")]
) -> str:
    """
    Validates the Server API Key (Admin Access).
    Uses constant-time comparison to prevent timing attacks.
    """
    if not settings.API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: API_SECRET not set"
        )

    if not secrets.compare_digest(x_api_key, settings.API_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-API-Key credentials"
        )
    return x_api_key

# --- BYOK (Bring Your Own Key) Dependencies ---

async def get_user_llm_key(
    x_user_llm_key: Annotated[Optional[str], Header(description="User's Gemini API Key (Optional)")] = None
) -> Optional[str]:
    """
    Extracts the user's personal LLM Key from headers.
    """
    return x_user_llm_key

def get_llm_adapter(
    user_key: Optional[str] = Depends(get_user_llm_key)
) -> GeminiAdapter:
    """
    Creates a request-scoped Adapter instance.
    Injects User Key if present, otherwise falls back to Server Key.
    """
    return GeminiAdapter(user_api_key=user_key)

# --- Use Case Injection ---

@inject
def get_generate_text_use_case(
    llm_adapter: GeminiAdapter = Depends(get_llm_adapter),
    engine: IGrammarEngine = Depends(get_grammar_engine)
) -> GenerateText:
    """
    Constructs the GenerateText Interactor.
    CRITICAL FIX: We pass 'engine' and 'llm' to match the Use Case __init__.
    """
    return GenerateText(engine=engine, llm=llm_adapter)

@inject
def get_build_language_use_case(
    use_case: BuildLanguage = Depends(Provide[Container.build_language_use_case])
) -> BuildLanguage:
    """Dependency to inject the BuildLanguage Interactor (Static)."""
    return use_case

@inject
def get_onboard_saga(
    llm_adapter: GeminiAdapter = Depends(get_llm_adapter),
    saga: OnboardLanguageSaga = Depends(Provide[Container.onboard_language_saga])
) -> OnboardLanguageSaga:
    """Dependency to inject the OnboardLanguageSaga."""
    # If saga needs the request-scoped LLM, set it here (optional pattern)
    # saga.llm = llm_adapter
    return saga