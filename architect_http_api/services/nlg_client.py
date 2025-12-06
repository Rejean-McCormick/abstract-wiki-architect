# architect_http_api/services/nlg_client.py

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Mapping, Optional, Sequence

from nlg.api import GenerationOptions, GenerationResult, NLGSession
from nlg.semantics import Frame


@dataclass
class NLGClientConfig:
    """
    Configuration for NLGClient.

    Attributes
    ----------
    preload_langs:
        Optional list of language codes to pre-initialize in the underlying
        NLG session (e.g. ["en", "fr"]). This avoids cold-start cost on the
        first request per language.
    """

    preload_langs: Optional[Sequence[str]] = None


class NLGClient:
    """
    Thin service wrapper around the core `nlg.api` frontend.

    Responsibilities
    ----------------
    - Own a long-lived `NLGSession` instance for this process.
    - Provide a stable, HTTP-friendly interface for generation calls.
    - Convert simple option payloads (dicts) into `GenerationOptions`.

    This service is deliberately kept generic: it works with any semantic
    `Frame` instance (bio, event, relational, narrative, etc.). Higher-level
    services (AI, frames, entities) are responsible for building the frames.
    """

    def __init__(self, config: Optional[NLGClientConfig] = None) -> None:
        if config is None:
            config = NLGClientConfig()

        preload_langs = list(config.preload_langs or [])
        self._session = NLGSession(preload_langs=preload_langs)
        # `NLGSession` may internally touch shared caches; protect calls with a lock
        # so the HTTP layer can safely use this from multiple worker threads.
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        *,
        lang: str,
        frame: Frame,
        options: Optional[GenerationOptions] = None,
        debug: bool = False,
    ) -> GenerationResult:
        """
        Generate text for a fully-constructed semantic frame.

        Parameters
        ----------
        lang:
            Target language code (e.g. "en", "fr", "sw").
        frame:
            Any semantic frame supported by the core NLG library.
        options:
            Optional `GenerationOptions`. If you only have a raw dict
            (e.g. from an HTTP payload), use `build_options` first.
        debug:
            If True, returns engine-specific debug information when available.

        Returns
        -------
        GenerationResult
        """
        with self._lock:
            return self._session.generate(
                lang=lang,
                frame=frame,
                options=options,
                debug=debug,
            )

    def generate_with_option_payload(
        self,
        *,
        lang: str,
        frame: Frame,
        option_payload: Optional[Mapping[str, Any]] = None,
        debug: bool = False,
    ) -> GenerationResult:
        """
        Convenience wrapper that accepts a raw options payload (dict).

        This is the typical entry point for HTTP handlers, which usually
        receive JSON like:

            {
                "lang": "en",
                "frame": { ... },          # handled elsewhere
                "options": {
                    "register": "neutral",
                    "max_sentences": 2
                },
                "debug": true
            }

        The caller is still responsible for constructing `frame` from JSON;
        this method only converts the `options` part into `GenerationOptions`.
        """
        options = self.build_options(option_payload)
        return self.generate(lang=lang, frame=frame, options=options, debug=debug)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def build_options(
        payload: Optional[Mapping[str, Any]],
    ) -> Optional[GenerationOptions]:
        """
        Construct `GenerationOptions` from a generic mapping.

        Expected keys (all optional):
        - register: str          # "neutral", "formal", "informal", ...
        - max_sentences: int
        - discourse_mode: str    # e.g. "intro", "summary"
        - seed: int              # reserved for future stochastic behavior

        Any missing keys are left as `None`, letting the core NLG layer
        apply its defaults.
        """
        if not payload:
            return None

        # Be permissive: tolerate extra keys and type mismatches where possible.
        register = payload.get("register")
        max_sentences = payload.get("max_sentences")
        discourse_mode = payload.get("discourse_mode")
        seed = payload.get("seed")

        # Basic type coercion where it is obviously safe.
        if max_sentences is not None:
            try:
                max_sentences = int(max_sentences)
            except (TypeError, ValueError):
                max_sentences = None

        if seed is not None:
            try:
                seed = int(seed)
            except (TypeError, ValueError):
                seed = None

        return GenerationOptions(
            register=str(register) if register is not None else None,
            max_sentences=max_sentences,
            discourse_mode=str(discourse_mode)
            if discourse_mode is not None
            else None,
            seed=seed,
        )


# Simple factory for integration with FastAPI dependency injection, if desired.

_default_client: Optional[NLGClient] = None


def get_nlg_client() -> NLGClient:
    """
    Process-local singleton accessor.

    Useful as a FastAPI dependency:

        nlg_client = Depends(get_nlg_client)

    so that all HTTP handlers share a single underlying `NLGSession`.
    """
    global _default_client
    if _default_client is None:
        _default_client = NLGClient()
    return _default_client
