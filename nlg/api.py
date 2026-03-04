# nlg/api.py

from __future__ import annotations

import asyncio
import inspect
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence, cast

from app.core.domain.models import Frame as WireFrame
from app.core.domain.models import Sentence
from app.core.ports.grammar_engine import IGrammarEngine
from app.shared.container import container


# Optional semantic-frame types (kept for compatibility with older call sites).
try:
    from app.core.domain.semantics.types import BioFrame as BioFrame  # type: ignore
except Exception:  # pragma: no cover
    BioFrame = Any  # type: ignore[misc,assignment]

try:
    # Not all branches define EventFrame; keep it optional.
    from app.core.domain.semantics.types import EventFrame as EventFrame  # type: ignore
except Exception:  # pragma: no cover
    EventFrame = Any  # type: ignore[misc,assignment]


# Public "Frame" type for this module: the current engine contract uses WireFrame.
Frame = WireFrame


# ---------------------------------------------------------------------------
# Public data models
# ---------------------------------------------------------------------------


@dataclass
class GenerationOptions:
    """
    High-level generation controls.

    Note: current engine contract is intentionally small; options are carried
    forward for compatibility but may be ignored by the underlying engine.
    """

    register: Optional[str] = None
    max_sentences: Optional[int] = None
    discourse_mode: Optional[str] = None
    seed: Optional[int] = None

    def to_engine_kwargs(self) -> Dict[str, Any]:
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
    frame: Any  # accept WireFrame or semantic frames passed by callers
    debug_info: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Engine protocol (adapter boundary)
# ---------------------------------------------------------------------------


class Engine(Protocol):
    """
    Minimal protocol expected from engines/adapters.

    The return value MUST be a dict with at least:
      - "text": str
      - optionally "sentences": list[str]
      - optionally "debug_info": dict
    """

    def generate(self, frame: Any, **kwargs: Any) -> Dict[str, Any]:
        ...


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_grammar_engine() -> IGrammarEngine:
    # DI container provides the configured grammar engine implementation.
    return cast(IGrammarEngine, container.grammar_engine())


def _run_async(coro: Any) -> Any:
    """
    Run an awaitable from sync code.

    If called while an event loop is already running, raise with guidance to
    use the async API.
    """
    if not inspect.isawaitable(coro):
        return coro

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    raise RuntimeError(
        "nlg.api.generate() was called from within a running event loop. "
        "Use NLGSession.generate_async(...) instead."
    )


def _coerce_to_wire_frame(frame: Any) -> WireFrame:
    """
    Accept several frame shapes and coerce into the WireFrame expected by IGrammarEngine.

    Supported inputs:
      - WireFrame (app.core.domain.models.Frame)
      - dict compatible with WireFrame
      - pydantic model with model_dump() producing WireFrame-compatible dict
      - legacy semantic BioFrame-like objects (best-effort)
    """
    if isinstance(frame, WireFrame):
        return frame

    if isinstance(frame, dict):
        # Pydantic v2
        return WireFrame.model_validate(frame)

    if hasattr(frame, "model_dump"):
        data = frame.model_dump()  # type: ignore[attr-defined]
        if isinstance(data, dict):
            return WireFrame.model_validate(data)

    # Best-effort adapter for legacy semantic BioFrame objects:
    # expects fields: main_entity.{name,gender}, primary_profession_lemmas, nationality_lemmas
    if hasattr(frame, "main_entity") and (
        hasattr(frame, "primary_profession_lemmas") or hasattr(frame, "nationality_lemmas")
    ):
        me = getattr(frame, "main_entity", None)
        name = getattr(me, "name", "") if me is not None else ""
        gender = getattr(me, "gender", "") if me is not None else ""

        prof = ""
        nat = ""

        try:
            profs = getattr(frame, "primary_profession_lemmas", None) or []
            if profs:
                prof = str(profs[0] or "")
        except Exception:
            prof = ""

        try:
            nats = getattr(frame, "nationality_lemmas", None) or []
            if nats:
                nat = str(nats[0] or "")
        except Exception:
            nat = ""

        props: Dict[str, Any] = {}
        if prof:
            props["primary_profession"] = prof
        if nat:
            props["nationality"] = nat

        return WireFrame(
            frame_type="bio",
            subject={"name": name, "gender": gender},
            properties=props,
        )

    raise TypeError(
        f"Unsupported frame type for generation: {type(frame).__name__}. "
        "Provide app.core.domain.models.Frame (WireFrame) or a compatible dict."
    )


def _split_sentences_fallback(text: str) -> List[str]:
    if not text.strip():
        return []
    chunks = re.split(r"([.!?])", text)
    sentences: List[str] = []
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
    leftover = buf.strip()
    if leftover:
        sentences.append(leftover)
    return sentences


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------


class _AppEngineAdapter:
    """
    Adapter around the app's configured IGrammarEngine (container-backed).
    """

    def __init__(self, lang: str) -> None:
        self.lang = lang
        self._engine = _get_grammar_engine()

    async def generate_async(self, frame: Any, **kwargs: Any) -> Dict[str, Any]:
        debug = bool(kwargs.get("debug", False))
        wire_frame = _coerce_to_wire_frame(frame)
        sentence: Sentence = await self._engine.generate(lang_code=self.lang, frame=wire_frame)
        out: Dict[str, Any] = {"text": sentence.text, "sentences": [sentence.text]}
        if debug:
            out["debug_info"] = sentence.debug_info
        return out

    def generate(self, frame: Any, **kwargs: Any) -> Dict[str, Any]:
        return _run_async(self.generate_async(frame, **kwargs))


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

    def generate(
        self,
        lang: str,
        frame: Any,
        *,
        options: Optional[GenerationOptions] = None,
        debug: bool = False,
    ) -> GenerationResult:
        engine = self._get_engine(lang)

        # Keep options for compatibility; engine may ignore.
        engine_kwargs = options.to_engine_kwargs() if options else {}
        engine_kwargs["debug"] = debug

        raw = engine.generate(frame, **engine_kwargs)

        text = str(raw.get("text", ""))

        sentences = raw.get("sentences")
        if sentences is None:
            sentences = _split_sentences_fallback(text)
        else:
            sentences = [str(s) for s in cast(Sequence[Any], sentences)]

        debug_info = raw.get("debug_info") if debug else None
        if debug and options is not None:
            debug_info = dict(debug_info or {})
            debug_info.setdefault("options", options.to_engine_kwargs())

        return GenerationResult(
            text=text,
            sentences=sentences,
            lang=lang,
            frame=frame,
            debug_info=debug_info,
        )

    async def generate_async(
        self,
        lang: str,
        frame: Any,
        *,
        options: Optional[GenerationOptions] = None,
        debug: bool = False,
    ) -> GenerationResult:
        """
        Async variant for callers already running an event loop.
        """
        engine = self._get_engine(lang)
        if not isinstance(engine, _AppEngineAdapter):
            # Fallback: run sync engine in thread-compatible way is out of scope here.
            # Keep behavior explicit.
            return self.generate(lang=lang, frame=frame, options=options, debug=debug)

        engine_kwargs = options.to_engine_kwargs() if options else {}
        engine_kwargs["debug"] = debug

        raw = await engine.generate_async(frame, **engine_kwargs)

        text = str(raw.get("text", ""))
        sentences = raw.get("sentences") or _split_sentences_fallback(text)

        debug_info = raw.get("debug_info") if debug else None
        if debug and options is not None:
            debug_info = dict(debug_info or {})
            debug_info.setdefault("options", options.to_engine_kwargs())

        return GenerationResult(
            text=text,
            sentences=[str(s) for s in sentences],
            lang=lang,
            frame=frame,
            debug_info=debug_info,
        )

    def _get_engine(self, lang: str) -> Engine:
        if lang in self._engine_cache:
            return self._engine_cache[lang]

        engine: Engine = _AppEngineAdapter(lang)
        self._engine_cache[lang] = engine
        return engine


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

_default_session = NLGSession()


def generate(
    lang: str,
    frame: Any,
    *,
    options: Optional[GenerationOptions] = None,
    debug: bool = False,
) -> GenerationResult:
    return _default_session.generate(lang=lang, frame=frame, options=options, debug=debug)


def generate_bio(
    lang: str,
    bio: Any,
    *,
    options: Optional[GenerationOptions] = None,
    debug: bool = False,
) -> GenerationResult:
    return generate(lang=lang, frame=bio, options=options, debug=debug)


def generate_event(
    lang: str,
    event: Any,
    *,
    options: Optional[GenerationOptions] = None,
    debug: bool = False,
) -> GenerationResult:
    return generate(lang=lang, frame=event, options=options, debug=debug)


__all__ = [
    "GenerationOptions",
    "GenerationResult",
    "Engine",
    "NLGSession",
    "generate",
    "generate_bio",
    "generate_event",
]