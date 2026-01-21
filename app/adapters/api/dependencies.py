# app/adapters/api/dependencies.py
from __future__ import annotations

import logging
import os
import re
import secrets
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.adapters.llm_adapter import GeminiAdapter
from app.core.ports.grammar_engine import IGrammarEngine
from app.core.use_cases.build_language import BuildLanguage
from app.core.use_cases.generate_text import GenerateText
from app.core.use_cases.onboard_language_saga import OnboardLanguageSaga
from app.shared.config import AppEnv, settings

# [FIX] REMOVED top-level import to break circular dependency
# from app.shared.container import container 

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Grammar Engine Dependency
# -----------------------------------------------------------------------------
def get_grammar_engine() -> IGrammarEngine:
    """Returns the process-wide singleton IGrammarEngine from the DI Container."""
    # [FIX] Lazy import: Only grab container when the function is CALLED
    from app.shared.container import container
    return container.grammar_engine()


# -----------------------------------------------------------------------------
# Security: Admin API key
# -----------------------------------------------------------------------------
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

DEFAULT_DEV_API_KEY = "dev-api-key"


def _configured_api_secret() -> Optional[str]:
    configured = getattr(settings, "API_SECRET", None) or getattr(settings, "API_KEY", None)
    if configured:
        return configured
    return os.getenv("API_SECRET") or os.getenv("API_KEY")


def _normalize_presented_key(x_api_key: Optional[str]) -> Optional[str]:
    if not x_api_key:
        return None
    key = x_api_key.strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key or None


def _split_secrets(configured: str) -> list[str]:
    parts = re.split(r"[,\s]+", configured.strip())
    return [p for p in parts if p]


def _is_valid_key(presented: str, configured: str) -> bool:
    for candidate in _split_secrets(configured):
        if secrets.compare_digest(presented, candidate):
            return True
    return False


async def verify_api_key(x_api_key: Optional[str] = Security(api_key_scheme)) -> str:
    """
    Validates the Server API Key (Admin Access).
    """
    configured = _configured_api_secret()

    # [FIX] DEV MODE BYPASS: If we are in development and no key is sent, allow access.
    # This fixes the 403 Forbidden error when running local tools that don't send headers.
    if settings.APP_ENV == AppEnv.DEVELOPMENT:
        if not x_api_key:
            return DEFAULT_DEV_API_KEY

    if not configured:
        if settings.APP_ENV == AppEnv.PRODUCTION:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server misconfiguration: API_SECRET is not set",
            )
        configured = DEFAULT_DEV_API_KEY

    presented = _normalize_presented_key(x_api_key)

    if not presented:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-API-Key header",
        )

    if not _is_valid_key(presented, configured):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-API-Key credentials",
        )

    return presented


# -----------------------------------------------------------------------------
# BYOK (Bring Your Own Key) LLM dependency
# -----------------------------------------------------------------------------
async def get_user_llm_key(
    x_user_llm_key: Annotated[
        Optional[str],
        Header(description="User's Gemini API Key (Optional)"),
    ] = None,
) -> Optional[str]:
    return x_user_llm_key


def get_llm_adapter(user_key: Optional[str] = Depends(get_user_llm_key)) -> GeminiAdapter:
    return GeminiAdapter(user_api_key=user_key)


# -----------------------------------------------------------------------------
# Use case injection
# -----------------------------------------------------------------------------
def get_generate_text_use_case(
    llm_adapter: GeminiAdapter = Depends(get_llm_adapter),
    engine: IGrammarEngine = Depends(get_grammar_engine),
) -> GenerateText:
    """Dependency to construct the GenerateText interactor."""
    return GenerateText(engine=engine, llm=llm_adapter)


def get_build_language_use_case() -> BuildLanguage:
    """Dependency to construct the BuildLanguage interactor."""
    # [FIX] Lazy import
    from app.shared.container import container
    return container.build_language_use_case()


def get_onboard_saga(
    llm_adapter: GeminiAdapter = Depends(get_llm_adapter),
) -> OnboardLanguageSaga:
    """Dependency to inject the OnboardLanguageSaga."""
    # [FIX] Lazy import
    from app.shared.container import container
    saga = container.onboard_language_saga()
    if hasattr(saga, "llm"):
        saga.llm = llm_adapter
    return saga