# app/adapters/api/dependencies.py
from __future__ import annotations

import logging
import re
import secrets
from threading import Lock
from typing import Annotated, Optional

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.adapters.engines.gf_wrapper import GFGrammarEngine
from app.adapters.llm_adapter import GeminiAdapter
from app.core.ports.grammar_engine import IGrammarEngine
from app.core.use_cases.build_language import BuildLanguage
from app.core.use_cases.generate_text import GenerateText
from app.core.use_cases.onboard_language_saga import OnboardLanguageSaga
from app.shared.config import AppEnv, settings
from app.shared.container import Container

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Grammar engine singleton (lazy)
# -----------------------------------------------------------------------------
_engine_lock = Lock()
_grammar_engine_instance: Optional[GFGrammarEngine] = None


def get_grammar_engine() -> IGrammarEngine:
    """
    Returns a process-wide singleton GFGrammarEngine.

    The GF engine is expensive to initialize (loads PGF + metadata). We keep one
    instance per process and reuse it across requests.
    """
    global _grammar_engine_instance
    if _grammar_engine_instance is None:
        with _engine_lock:
            if _grammar_engine_instance is None:
                _grammar_engine_instance = GFGrammarEngine()

    assert _grammar_engine_instance is not None
    return _grammar_engine_instance


# -----------------------------------------------------------------------------
# Security: Admin API key
# -----------------------------------------------------------------------------
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def _configured_api_secret() -> Optional[str]:
    """
    Returns the configured server API secret.

    Backwards-compatible: also checks legacy setting/API env naming.
    """
    configured = getattr(settings, "API_SECRET", None) or getattr(settings, "API_KEY", None)
    if configured:
        return configured

    # Fallback in case settings were initialized before env injection in some edge paths
    import os

    return os.getenv("API_SECRET") or os.getenv("API_KEY")


def _normalize_presented_key(x_api_key: Optional[str]) -> Optional[str]:
    if not x_api_key:
        return None
    key = x_api_key.strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key or None


def _split_secrets(configured: str) -> list[str]:
    # Allow comma-separated or whitespace-separated lists for rotation/multi-key setups.
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

    - In PRODUCTION: fails closed if API_SECRET is missing.
    - In DEVELOPMENT/TESTING: if API_SECRET is missing, auth is bypassed
      (returns "dev-bypass") for local workflows.
    """
    configured = _configured_api_secret()
    presented = _normalize_presented_key(x_api_key)

    if not configured:
        if settings.APP_ENV == AppEnv.PRODUCTION:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server misconfiguration: API_SECRET is not set",
            )
        return "dev-bypass"

    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
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
    """Extracts the user's personal LLM key from headers."""
    return x_user_llm_key


def get_llm_adapter(user_key: Optional[str] = Depends(get_user_llm_key)) -> GeminiAdapter:
    """
    Creates a request-scoped LLM adapter.

    If user_key is provided, it is used; otherwise the adapter falls back to
    server configuration (settings.GEMINI_API_KEY) internally.
    """
    return GeminiAdapter(user_api_key=user_key)


# -----------------------------------------------------------------------------
# Use case injection
# -----------------------------------------------------------------------------
@inject
def get_generate_text_use_case(
    llm_adapter: GeminiAdapter = Depends(get_llm_adapter),
    engine: IGrammarEngine = Depends(get_grammar_engine),
) -> GenerateText:
    """Dependency to construct the GenerateText interactor."""
    return GenerateText(engine=engine, llm=llm_adapter)


@inject
def get_build_language_use_case(
    use_case: BuildLanguage = Depends(Provide[Container.build_language_use_case]),
) -> BuildLanguage:
    """Dependency to inject the BuildLanguage interactor (container-managed)."""
    return use_case


@inject
def get_onboard_saga(
    llm_adapter: GeminiAdapter = Depends(get_llm_adapter),
    saga: OnboardLanguageSaga = Depends(Provide[Container.onboard_language_saga]),
) -> OnboardLanguageSaga:
    """Dependency to inject the OnboardLanguageSaga (container-managed)."""
    if hasattr(saga, "llm"):
        saga.llm = llm_adapter
    return saga
