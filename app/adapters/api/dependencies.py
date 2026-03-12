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

logger = logging.getLogger(__name__)


def _get_container():
    """
    Lazy container import to avoid circular imports during module import time.
    """
    from app.shared.container import container

    return container


# -----------------------------------------------------------------------------
# Grammar Engine Dependency
# -----------------------------------------------------------------------------
def get_grammar_engine() -> IGrammarEngine:
    """Returns the process-wide singleton IGrammarEngine from the DI container."""
    return _get_container().grammar_engine()


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
    Validates the server API key.
    """
    configured = _configured_api_secret()

    if settings.APP_ENV == AppEnv.DEVELOPMENT and not x_api_key:
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
    """
    Builds a request-scoped Gemini adapter.

    BYOK behavior:
    - X-User-LLM-Key header wins
    - falls back to server env vars inside GeminiAdapter
    """
    return GeminiAdapter(user_api_key=user_key)


# -----------------------------------------------------------------------------
# Use case injection
# -----------------------------------------------------------------------------
def get_generate_text_use_case(
    llm_adapter: GeminiAdapter = Depends(get_llm_adapter),
) -> GenerateText:
    """
    Resolve GenerateText from the DI container, then attach the request-scoped
    LLM adapter so BYOK stays request-aware while the canonical runtime wiring
    remains container-owned.
    """
    use_case = _get_container().generate_text_use_case()

    # The current GenerateText use case exposes `llm` as an optional dependency.
    # We attach the request-scoped adapter after resolution because the container
    # provider is currently the canonical owner of engine/runtime wiring.
    if hasattr(use_case, "llm"):
        use_case.llm = llm_adapter

    return use_case


def get_build_language_use_case() -> BuildLanguage:
    """Resolve BuildLanguage from the DI container."""
    return _get_container().build_language_use_case()


def get_onboard_saga(
    llm_adapter: GeminiAdapter = Depends(get_llm_adapter),
) -> OnboardLanguageSaga:
    """
    Resolve the onboarding saga from the DI container.

    Kept BYOK-compatible for future saga variants that may expose an `llm`
    attribute, without requiring the current saga constructor to change.
    """
    saga = _get_container().onboard_language_saga()

    if hasattr(saga, "llm"):
        saga.llm = llm_adapter

    return saga