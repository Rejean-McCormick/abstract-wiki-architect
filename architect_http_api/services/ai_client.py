# architect_http_api/services/ai_client.py

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AIClientConfig:
    """
    Configuration for the AIClient.

    Values are typically loaded from environment variables so the HTTP API can
    run without hard-coding any provider-specific details.

    Supported providers (for now):
      - "none"     → offline / echo-style fallback (no external calls)
      - "openai"   → OpenAI Chat Completions API (if `openai` lib is installed)
      - "anthropic"→ Anthropic Messages API (if `anthropic` lib is installed)
    """

    provider: str = "none"
    model: Optional[str] = None
    api_key: Optional[str] = None
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "AIClientConfig":
        """
        Build config from environment variables.

        Environment variables:
            ARCHITECT_AI_PROVIDER: "none" | "openai" | "anthropic"
            ARCHITECT_AI_MODEL:    default model name
            OPENAI_API_KEY:        used when provider == "openai"
            ANTHROPIC_API_KEY:     used when provider == "anthropic"
            ARCHITECT_AI_TIMEOUT:  optional, seconds (float)
        """
        provider = os.getenv("ARCHITECT_AI_PROVIDER", "none").strip().lower()

        # Generic model override; can be provider-specific in the future.
        model = os.getenv("ARCHITECT_AI_MODEL")

        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
        else:
            api_key = None

        timeout_str = os.getenv("ARCHITECT_AI_TIMEOUT")
        timeout: float
        try:
            timeout = float(timeout_str) if timeout_str is not None else 30.0
        except ValueError:
            timeout = 30.0

        return cls(provider=provider, model=model, api_key=api_key, timeout=timeout)


class AIClient:
    """
    Thin abstraction layer over external LLM providers.

    This keeps the rest of the HTTP API independent from any concrete AI SDK.
    Routers and services should depend on this class instead of importing
    `openai`, `anthropic`, etc. directly.

    The primary entry point for now is `chat`, which follows an OpenAI-style
    messages format:

        messages = [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
            ...
        ]

    If no provider is configured (or the provider SDK is missing), the client
    falls back to a deterministic, offline behaviour that simply returns a
    short echo / summary of the latest user message. This is useful for local
    development and for running tests without network access.
    """

    def __init__(self, config: Optional[AIClientConfig] = None) -> None:
        self.config = config or AIClientConfig.from_env()
        self._client: Any = None  # provider-specific client instance
        self._init_client()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> str:
        """
        Run a chat-style completion and return the main text response.

        Args:
            messages:
                List of role/content dicts, OpenAI-style. The caller is
                responsible for providing at least one user message.
            system_prompt:
                Optional high-level instruction that is prepended as a
                `"system"` message.
            max_tokens:
                Upper bound on the length of the generated answer.
            temperature:
                Sampling temperature; higher means more diverse, lower more
                deterministic.

        Returns:
            The assistant's reply as a plain string. If no external provider
            is configured or reachable, a local fallback is used.
        """
        if system_prompt:
            messages = [
                {"role": "system", "content": system_prompt},
                *messages,
            ]

        provider = self.config.provider

        if provider == "openai" and self._client is not None:
            try:
                return self._chat_openai(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("OpenAI chat failed, falling back to local echo: %s", exc)

        elif provider == "anthropic" and self._client is not None:
            try:
                return self._chat_anthropic(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Anthropic chat failed, falling back to local echo: %s", exc)

        # Fallback: offline behaviour (no external AI).
        return self._offline_fallback(messages)

    # ------------------------------------------------------------------
    # Internal setup
    # ------------------------------------------------------------------

    def _init_client(self) -> None:
        """
        Initialize provider-specific client instance, if possible.

        This method is intentionally tolerant: if the provider is unknown or
        the SDK is not installed, it logs a warning and keeps `_client` as
        None so that the offline fallback can be used.
        """
        provider = self.config.provider

        if provider == "openai":
            self._init_openai()
        elif provider == "anthropic":
            self._init_anthropic()
        elif provider in ("none", "", None):
            logger.info("AI provider disabled (ARCHITECT_AI_PROVIDER=none).")
        else:
            logger.warning("Unknown AI provider '%s'; falling back to offline mode.", provider)

    def _init_openai(self) -> None:
        api_key = self.config.api_key
        if not api_key:
            logger.warning("OPENAI_API_KEY not set; OpenAI provider disabled.")
            return

        try:
            import openai  # type: ignore[import]
        except ImportError:  # pragma: no cover - depends on environment
            logger.warning("openai package not installed; OpenAI provider disabled.")
            return

        # Support both legacy and >=1.0 styles.
        client: Any
        if hasattr(openai, "OpenAI"):
            client = openai.OpenAI(api_key=api_key)
        else:
            # Legacy: module-level client
            openai.api_key = api_key  # type: ignore[attr-defined]
            client = openai

        self._client = client
        logger.info("OpenAI client initialized.")

    def _init_anthropic(self) -> None:
        api_key = self.config.api_key
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set; Anthropic provider disabled.")
            return

        try:
            import anthropic  # type: ignore[import]
        except ImportError:  # pragma: no cover - depends on environment
            logger.warning("anthropic package not installed; Anthropic provider disabled.")
            return

        client: Any
        if hasattr(anthropic, "Anthropic"):
            client = anthropic.Anthropic(api_key=api_key)
        else:
            # Legacy SDK
            client = anthropic.Client(api_key=api_key)  # type: ignore[attr-defined]

        self._client = client
        logger.info("Anthropic client initialized.")

    # ------------------------------------------------------------------
    # Provider-specific chat implementations
    # ------------------------------------------------------------------

    def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """
        Call OpenAI's chat API using whichever client style is available.
        """
        client = self._client
        model = self.config.model or "gpt-4.1-mini"

        # New-style client (openai>=1.0.0)
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.config.timeout,  # type: ignore[arg-type]
            )
            choice = response.choices[0]
            # `message.content` can be string or list depending on SDK;
            # keep it simple and coerce to string.
            content = getattr(choice.message, "content", "")
            return str(content)

        # Legacy module-level interface
        if hasattr(client, "ChatCompletion"):
            response = client.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.config.timeout,
            )
            return str(response["choices"][0]["message"]["content"])

        raise RuntimeError("OpenAI client does not expose a known chat interface.")

    def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """
        Call Anthropic's Messages API (preferred) or legacy completions.
        """
        client = self._client
        model = self.config.model or "claude-3-5-sonnet-20240620"

        # Convert OpenAI-style history into Anthropic-style user/assistant turns.
        # We ignore system messages here; they are passed separately where supported.
        user_content_parts: List[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                user_content_parts.append(content)
            elif role == "assistant":
                user_content_parts.append(f"[assistant] {content}")
            elif role == "system":
                user_content_parts.append(f"[system] {content}")
        merged_content = "\n\n".join(user_content_parts)

        # New-style Messages API
        if hasattr(client, "messages"):
            response = client.messages.create(  # type: ignore[attr-defined]
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": merged_content}],
            )
            # Response content is typically a list of blocks; concatenate text blocks.
            pieces: List[str] = []
            for block in getattr(response, "content", []) or []:
                if getattr(block, "type", None) == "text":
                    pieces.append(getattr(block, "text", ""))
            return "\n".join(pieces).strip()

        # Legacy completions API
        if hasattr(client, "completions"):
            completion = client.completions.create(  # type: ignore[attr-defined]
                model=model,
                max_tokens_to_sample=max_tokens,
                temperature=temperature,
                prompt=merged_content,
            )
            return str(getattr(completion, "completion", "")).strip()

        raise RuntimeError("Anthropic client does not expose a known messages/completions interface.")

    # ------------------------------------------------------------------
    # Offline fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _offline_fallback(messages: List[Dict[str, str]]) -> str:
        """
        Deterministic, no-network fallback behaviour.

        This is deliberately simple: it inspects the last user message and
        returns a short echo / summary string. This keeps HTTP endpoints
        predictable in environments where no AI provider is configured.
        """
        last_user: Optional[str] = None
        for msg in messages:
            if msg.get("role") == "user":
                last_user = msg.get("content", "") or last_user

        if not last_user:
            return "AI helper is not configured; no user input to respond to."

        # Truncate to a reasonable preview length for safety.
        preview = last_user.strip().replace("\n", " ")
        if len(preview) > 240:
            preview = preview[:237].rstrip() + "..."

        return f"(offline AI fallback) Based on your input: {preview}"


__all__ = ["AIClientConfig", "AIClient"]
