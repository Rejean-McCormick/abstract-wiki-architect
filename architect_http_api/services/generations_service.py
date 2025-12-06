# architect_http_api/services/generations_service.py

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional

from nlg.api import GenerationOptions, GenerationResult

from architect_http_api.services.nlg_client import NLGClient


class GenerationsService:
    """
    High-level orchestration around the NLG layer for single generation requests.

    Responsibilities:
      * Accept normalized HTTP-level payloads (lang, frame_slug, payload, options).
      * Delegate to the NLG client to build the semantic frame and call the engines.
      * Normalize the `GenerationResult` into a JSON-friendly dict that the router
        can return directly from FastAPI / Starlette.

    This service is intentionally stateless. Any persistence / logging of generations
    should be handled by a separate repository or logging service and wired in at the
    router layer or via a decorator.
    """

    def __init__(self, nlg_client: NLGClient) -> None:
        self._nlg_client = nlg_client

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def generate(
        self,
        *,
        lang: str,
        frame_slug: str,
        payload: Dict[str, Any],
        options: Optional[GenerationOptions] = None,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """
        Run a single generation given a frame slug and raw JSON payload.

        Parameters
        ----------
        lang:
            Target language code (e.g. "en", "fr", "sw").
        frame_slug:
            Frontend / registry slug identifying which frame family / variant to use
            (e.g. "bio.person.simple", "event.historical", etc.).
        payload:
            Frame data as a JSON-compatible dict. The exact shape depends on the
            frame family and is interpreted by the NLG client / frame builder.
        options:
            Optional `GenerationOptions` instance. If you only have a dict (e.g. from
            HTTP), use `GenerationsService.build_options_from_dict` first.
        debug:
            If True, include any available debug information from the engine.

        Returns
        -------
        dict
            A JSON-serializable representation of the generation result, with a
            stable, frontend-friendly shape.
        """
        result = self._nlg_client.generate_from_payload(
            lang=lang,
            frame_slug=frame_slug,
            payload=payload,
            options=options,
            debug=debug,
        )

        return self._serialize_result(
            result=result,
            frame_slug=frame_slug,
            include_debug=debug,
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def build_options_from_dict(
        raw: Optional[Dict[str, Any]],
    ) -> Optional[GenerationOptions]:
        """
        Convert a loose HTTP options dict into a `GenerationOptions` instance.

        Expected keys (all optional) in `raw`:
          * register: str | None
          * max_sentences: int | None
          * discourse_mode: str | None
          * seed: int | None
        """
        if not raw:
            return None

        return GenerationOptions(
            register=raw.get("register"),
            max_sentences=raw.get("max_sentences"),
            discourse_mode=raw.get("discourse_mode"),
            seed=raw.get("seed"),
        )

    @staticmethod
    def _serialize_result(
        *,
        result: GenerationResult,
        frame_slug: str,
        include_debug: bool,
    ) -> Dict[str, Any]:
        """
        Normalize `GenerationResult` into a stable JSON-friendly dict.

        The exact shape is designed to be convenient for the frontend and tests.
        """
        frame = result.frame

        # Try to expose the underlying frame as a plain dict when possible.
        if is_dataclass(frame):
            raw_frame: Optional[Dict[str, Any]] = asdict(frame)
        elif hasattr(frame, "to_dict") and callable(getattr(frame, "to_dict")):
            raw_frame = frame.to_dict()  # type: ignore[assignment]
        else:
            # Fallback: we keep this nullable instead of guessing.
            raw_frame = None

        frame_type = getattr(frame, "frame_type", None)

        data: Dict[str, Any] = {
            "text": result.text,
            "sentences": list(result.sentences),
            "lang": result.lang,
            "frame_slug": frame_slug,
            "frame_type": frame_type,
            "raw_frame": raw_frame,
        }

        # Normalize debug_info to a predictable key, but only populate when asked.
        if include_debug:
            data["debug_info"] = result.debug_info or {}
        else:
            data["debug_info"] = None

        return data
