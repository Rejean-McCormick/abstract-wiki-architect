# nlg/api.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

import router
from .semantics import Frame, BioFrame, EventFrame

import re


# ---------------------------------------------------------------------------
# Public data models
# ---------------------------------------------------------------------------


@dataclass
class GenerationOptions:
    """
    High-level generation controls.

    This is intentionally small and stable. Low-level knobs (morphology, etc.)
    should remain internal to engines / language profiles.
    """

    register: Optional[str] = None  # "neutral", "formal", "informal", etc.
    max_sentences: Optional[int] = None  # Upper bound on number of sentences
    discourse_mode: Optional[str] = None  # e.g. "intro", "summary"
    seed: Optional[int] = None  # Reserved for future stochastic behavior

    def to_engine_kwargs(self) -> Dict[str, Any]:
        """
        Convert to a dict suitable for passing into engines. Engines may ignore
        fields they do not understand.
        """
        data: Dict[str, Any] = {}
        if self.register is not None:
            data["register"] = self.register
        if self.max_sentences is not None:
            data["max_sentences"] = self.max_sentences
        if self.discourse_mode is not None:
            data["discourse_mode"] = self.discourse_mode
        if self.seed is not None:
            data["seed"] = self.seed
        return data


@dataclass
class GenerationResult:
    """
    Standardized output from the frontend API.
    """

    text: str
    sentences: List[str]
    lang: str
    frame: Frame
    debug_info: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Engine protocol (adapter boundary)
# ---------------------------------------------------------------------------


class Engine(Protocol):
    """
    Minimal protocol expected from family/language engines.

    You should implement this in your existing engines, either by:
      - Adding a `generate` method with this signature, or
      - Providing an adapter that wraps current engine APIs.

    The return value MUST be a dict with at least:
      - "text": str
      - optionally "sentences": list[str]
      - optionally "debug_info": dict
    """

    def generate(
        self,
        frame: Frame,
        **kwargs: Any,
    ) -> Dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class NLGSession:
    """
    Stateful session that caches engines and other resources.

    Use this in long-running services or batch jobs.
    """

    def __init__(self, *, preload_langs: Optional[List[str]] = None) -> None:
        self._engine_cache: Dict[str, Engine] = {}
        if preload_langs:
            for lang in preload_langs:
                self._get_engine(lang)

    # public API -------------------------------------------------------------

    def generate(
        self,
        lang: str,
        frame: Frame,
        *,
        options: Optional[GenerationOptions] = None,
        debug: bool = False,
    ) -> GenerationResult:
        """
        Main entry point: frame → text.
        """
        engine = self._get_engine(lang)
        engine_kwargs = options.to_engine_kwargs() if options else {}
        engine_kwargs["debug"] = debug

        raw = engine.generate(frame, **engine_kwargs)

        text = str(raw.get("text", ""))

        sentences = raw.get("sentences")
        if sentences is None:
            # Simple, language-agnostic fallback.
            # Engines are encouraged to provide proper sentence segmentation.
            if text.strip():
                # Split on ., ! or ? while keeping the punctuation.
                chunks = re.split(r"([.!?])", text)
                sentences = []
                buf = ""
                for piece in chunks:
                    if not piece:
                        continue
                    buf += piece
                    if piece in ".!?":
                        sentence = buf.strip()
                        if sentence:
                            sentences.append(sentence)
                        buf = ""
                # Any leftover text without final punctuation:
                leftover = buf.strip()
                if leftover:
                    sentences.append(leftover)
            else:
                sentences = []

        debug_info = raw.get("debug_info") if debug else None

        return GenerationResult(
            text=text,
            sentences=sentences,
            lang=lang,
            frame=frame,
            debug_info=debug_info,
        )

    # internal helpers -------------------------------------------------------

    def _get_engine(self, lang: str) -> Engine:
        """
        Retrieve or initialize the engine for a given language.

        This assumes that `router.get_engine(lang)` MAY exist and return an
        object implementing the `Engine` protocol. If not, we fall back to a
        thin adapter around `router.render_bio(...)` for BioFrame-only usage.
        """
        if lang in self._engine_cache:
            return self._engine_cache[lang]

        if hasattr(router, "get_engine"):
            # If/when router exposes a proper engine factory, prefer that.
            engine: Engine = router.get_engine(lang)  # type: ignore[assignment]
        else:
            # Current codebase path: use a simple adapter around router.render_bio.
            engine = _RouterAdapter(lang)

        self._engine_cache[lang] = engine
        return engine


class _RouterAdapter:
    """
    Minimal adapter so the new frontend API can talk to the current router.

    For now this only supports BioFrame → `router.render_bio(...)`.
    Other frame types are left to future, richer integrations.
    """

    def __init__(self, lang: str) -> None:
        self.lang = lang

    def generate(self, frame: Frame, **kwargs: Any) -> Dict[str, Any]:
        # BioFrame → single biography sentence via router.render_bio
        if isinstance(frame, BioFrame):
            prof = (
                frame.primary_profession_lemmas[0]
                if frame.primary_profession_lemmas
                else ""
            )
            nat = frame.nationality_lemmas[0] if frame.nationality_lemmas else ""

            # Guard against missing main entity to avoid AttributeError.
            name = getattr(frame.main_entity, "name", "") or ""
            gender = getattr(frame.main_entity, "gender", "") or ""

            text = router.render_bio(
                name=name,
                gender=gender,
                profession_lemma=prof,
                nationality_lemma=nat,
                lang_code=self.lang,
            )
            return {"text": text, "sentences": [text]}

        # Placeholder for future EventFrame / other frames integration.
        if isinstance(frame, EventFrame):
            # Until router exposes a general `render_from_semantics` API,
            # we return an empty shell here.
            return {"text": "", "sentences": []}

        # Fallback for unknown frame types
        return {"text": "", "sentences": []}


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

# Default process-global session for simple/stateless usage.
_default_session = NLGSession()


def generate(
    lang: str,
    frame: Frame,
    *,
    options: Optional[GenerationOptions] = None,
    debug: bool = False,
) -> GenerationResult:
    """
    Stateless convenience wrapper around `NLGSession.generate`.

    Suitable for scripts, tests, and simple integrations.
    """
    return _default_session.generate(
        lang=lang,
        frame=frame,
        options=options,
        debug=debug,
    )


def generate_bio(
    lang: str,
    bio: BioFrame,
    *,
    options: Optional[GenerationOptions] = None,
    debug: bool = False,
) -> GenerationResult:
    """
    Convenience wrapper for biography frames.
    """
    return generate(
        lang=lang,
        frame=bio,
        options=options,
        debug=debug,
    )


def generate_event(
    lang: str,
    event: EventFrame,
    *,
    options: Optional[GenerationOptions] = None,
    debug: bool = False,
) -> GenerationResult:
    """
    Convenience wrapper for event frames.
    """
    return generate(
        lang=lang,
        frame=event,
        options=options,
        debug=debug,
    )


__all__ = [
    "GenerationOptions",
    "GenerationResult",
    "Engine",
    "NLGSession",
    "generate",
    "generate_bio",
    "generate_event",
]
