# app/adapters/engines/gf_wrapper.py
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Sequence

import structlog

try:
    import pgf
except ImportError:
    pgf = None

from app.core.domain.frame import BioFrame
from app.core.domain.models import Frame, Sentence
from app.shared.config import settings

try:
    from app.core.domain.models import SurfaceResult as _ImportedSurfaceResult
except Exception:
    _ImportedSurfaceResult = None

if TYPE_CHECKING:
    from app.core.domain.planning.construction_plan import ConstructionPlan

logger = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class _FallbackSurfaceResult:
    text: str
    lang_code: str
    construction_id: str
    renderer_backend: str
    fallback_used: bool = False
    tokens: tuple[str, ...] = field(default_factory=tuple)
    debug_info: dict[str, Any] = field(default_factory=dict)


def _get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(k): v for k, v in value.items()}
    return {}


def _clean_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    cleaned = str(value).strip()
    return cleaned or None


def _normalize_tokens(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, str):
        stripped = value.strip()
        return tuple(part for part in stripped.split() if part)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        tokens: list[str] = []
        for item in value:
            token = _clean_optional_str(item)
            if token:
                tokens.append(token)
        return tuple(tokens)

    return ()


def _build_surface_result(
    *,
    text: str,
    lang_code: str,
    construction_id: str,
    renderer_backend: str,
    fallback_used: bool,
    tokens: tuple[str, ...],
    debug_info: dict[str, Any],
) -> Any:
    if _ImportedSurfaceResult is not None:
        try:
            return _ImportedSurfaceResult(
                text=text,
                lang_code=lang_code,
                construction_id=construction_id,
                renderer_backend=renderer_backend,
                fallback_used=fallback_used,
                tokens=list(tokens),
                debug_info=debug_info,
            )
        except TypeError:
            pass

    return _FallbackSurfaceResult(
        text=text,
        lang_code=lang_code,
        construction_id=construction_id,
        renderer_backend=renderer_backend,
        fallback_used=fallback_used,
        tokens=tokens,
        debug_info=debug_info,
    )


class GFGrammarEngine:
    """
    GF/PGF-backed grammar adapter.

    Batch 6 role:
    - Authoritative renderer-facing entrypoint: `realize(construction_plan)`.
    - Compatibility shim retained: `generate(lang_code, frame) -> Sentence`.

    Runtime behavior:
    - Async server path lazily loads PGF via `await _ensure_grammar()`.
    - Sync tooling path can safely touch `.grammar` and trigger a blocking load
      when no event loop is running.

    Supported canonical slice:
    - bio / equative / classificatory constructions backed by:
        mkBioFull / mkBioProf / mkBioNat
    - basic eventive constructions backed by:
        mkEvent
    """

    renderer_backend = "gf"
    backend_name = "gf"

    _BIO_FRAME_TYPES = {
        "bio",
        "biography",
        "entity.person",
        "entity_person",
        "person",
        "entity.person.v1",
        "entity.person.v2",
    }

    _NAME_KEYS = ("name", "label", "title")
    _PROF_KEYS = ("profession", "occupation", "profession_lemma", "prof_lemma")
    _NAT_KEYS = ("nationality", "citizenship", "nationality_lemma", "nat_lemma")
    _GENDER_KEYS = ("gender", "sex")
    _QID_KEYS = ("qid", "id", "wikidata_qid")

    _SUBJECT_SLOT_KEYS = ("subject", "topic", "agent", "main_entity", "entity", "person")
    _PROF_SLOT_KEYS = ("profession", "occupation", "predicate_nominal", "predicate")
    _NAT_SLOT_KEYS = ("nationality", "citizenship", "predicate_nominal")
    _EVENT_SLOT_KEYS = ("event", "predicate", "event_obj", "comment", "theme")

    _BIO_CONSTRUCTION_IDS = frozenset(
        {
            "bio",
            "biography",
            "copula_equative_simple",
            "copula_equative_classification",
            "topic_comment_copular",
        }
    )
    _EVENT_CONSTRUCTION_IDS = frozenset(
        {
            "intransitive_event",
            "transitive_event",
            "ditransitive_event",
            "passive_event",
            "topic_comment_eventive",
            "causative_event",
        }
    )

    def __init__(self, lib_path: str | None = None):
        configured = (
            lib_path
            or os.getenv("PGF_PATH")
            or getattr(settings, "PGF_PATH", None)
            or os.getenv("AW_PGF_PATH")
            or getattr(settings, "AW_PGF_PATH", "gf/semantik_architect.pgf")
        )
        self.pgf_path: str = str(self._resolve_path(configured))

        self._grammar: Optional[Any] = None

        # Inventory (from rgl_inventory.json)
        self.inventory: Dict[str, Any] = {}

        # Language normalization maps
        self.wiki_to_iso2: Dict[str, str] = {}
        self.iso2_to_wiki: Dict[str, str] = {}
        self.iso2_to_iso3: Dict[str, str] = {}

        # Diagnostics
        self.last_load_error: Optional[str] = None
        self.last_load_error_type: Optional[str] = None

        self._async_load_lock: asyncio.Lock = asyncio.Lock()
        self._thread_load_lock: threading.Lock = threading.Lock()

        self._load_inventory()
        self._load_iso_config()
        self._derive_wiki_from_inventory()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    def _resolve_path(self, p: str | Path) -> Path:
        path = Path(p)

        if path.exists() and path.is_dir():
            path = path / "semantik_architect.pgf"

        if path.is_absolute():
            return path

        base = getattr(settings, "FILESYSTEM_REPO_PATH", None)
        if base:
            return (Path(base) / path).resolve()

        project_root = Path(__file__).resolve().parents[3]
        return (project_root / path).resolve()

    # ------------------------------------------------------------------
    # Grammar access (sync tooling compatibility)
    # ------------------------------------------------------------------
    @property
    def grammar(self) -> Optional[Any]:
        if self._grammar is not None:
            return self._grammar

        try:
            asyncio.get_running_loop()
            return None
        except RuntimeError:
            self._load_grammar_sync()
            return self._grammar

    @grammar.setter
    def grammar(self, value: Optional[Any]) -> None:
        self._grammar = value

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------
    def _load_inventory(self) -> None:
        try:
            candidates: list[Path] = []
            if settings and getattr(settings, "FILESYSTEM_REPO_PATH", None):
                repo_root = Path(settings.FILESYSTEM_REPO_PATH)
                candidates.append(repo_root / "data" / "indices" / "rgl_inventory.json")

            candidates.append(Path(__file__).resolve().parents[3] / "data" / "indices" / "rgl_inventory.json")

            inventory_path: Optional[Path] = None
            for p in candidates:
                if p.exists():
                    inventory_path = p
                    break

            if inventory_path:
                with inventory_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.inventory = data.get("languages", {}) or {}
        except Exception:
            self.inventory = {}

    def _load_iso_config(self) -> None:
        self.wiki_to_iso2 = {}
        self.iso2_to_wiki = {}
        self.iso2_to_iso3 = {}

        try:
            candidates: list[Path] = []
            if settings and getattr(settings, "FILESYSTEM_REPO_PATH", None):
                repo_root = Path(settings.FILESYSTEM_REPO_PATH)
                candidates.append(repo_root / "data" / "config" / "iso_to_wiki.json")
                candidates.append(repo_root / "config" / "iso_to_wiki.json")

            project_root = Path(__file__).resolve().parents[3]
            candidates.append(project_root / "data" / "config" / "iso_to_wiki.json")
            candidates.append(project_root / "config" / "iso_to_wiki.json")

            config_path: Optional[Path] = None
            for p in candidates:
                if p.exists():
                    config_path = p
                    break

            if not config_path:
                return

            with config_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)

            if not isinstance(raw, dict):
                return

            def _strip_wiki_prefix(s: str) -> str:
                t = (s or "").strip()
                if t.casefold().startswith("wiki") and len(t) > 4:
                    return t[4:]
                return t

            for k, v in raw.items():
                if not isinstance(k, str):
                    continue
                kk = k.strip().casefold()
                if not kk:
                    continue

                if isinstance(v, dict):
                    iso2 = v.get("iso2")
                    if not (isinstance(iso2, str) and len(iso2.strip()) == 2):
                        iso2 = kk if len(kk) == 2 and kk.isalpha() else None
                    else:
                        iso2 = iso2.strip().casefold()

                    wiki = v.get("wiki")
                    wiki_code = None
                    if isinstance(wiki, str) and wiki.strip():
                        wiki_code = _strip_wiki_prefix(wiki.strip())

                    iso3 = v.get("iso3") or v.get("iso_639_3") or v.get("iso639_3")
                    iso3_code = None
                    if isinstance(iso3, str) and iso3.strip():
                        iso3c = iso3.strip().casefold()
                        if len(iso3c) == 3 and iso3c.isalpha():
                            iso3_code = iso3c

                    if iso2 and len(iso2) == 2:
                        self.wiki_to_iso2[iso2] = iso2
                        self.wiki_to_iso2[f"wiki{iso2}"] = iso2

                        if wiki_code:
                            self.iso2_to_wiki[iso2] = wiki_code
                            self.wiki_to_iso2[wiki_code.casefold()] = iso2
                            self.wiki_to_iso2[f"wiki{wiki_code.casefold()}"] = iso2

                        if iso3_code:
                            self.iso2_to_iso3[iso2] = iso3_code
                            self.wiki_to_iso2[iso3_code] = iso2
                            self.wiki_to_iso2[f"wiki{iso3_code}"] = iso2

                elif isinstance(v, str):
                    vv = v.strip().casefold()
                    if not vv:
                        continue

                    if len(vv) == 2 and vv.isalpha():
                        self.wiki_to_iso2[kk] = vv
                        if kk.startswith("wiki") and len(kk) > 4:
                            self.wiki_to_iso2[kk[4:]] = vv
                        self.wiki_to_iso2[vv] = vv
                        self.wiki_to_iso2[f"wiki{vv}"] = vv
                        continue

                    if len(kk) == 2 and kk.isalpha():
                        iso2 = kk
                        wiki_code = _strip_wiki_prefix(v.strip())
                        if wiki_code:
                            self.iso2_to_wiki[iso2] = wiki_code
                            self.wiki_to_iso2[iso2] = iso2
                            self.wiki_to_iso2[f"wiki{iso2}"] = iso2
                            self.wiki_to_iso2[wiki_code.casefold()] = iso2
                            self.wiki_to_iso2[f"wiki{wiki_code.casefold()}"] = iso2

        except Exception:
            self.wiki_to_iso2 = {}
            self.iso2_to_wiki = {}
            self.iso2_to_iso3 = {}

    def _derive_wiki_from_inventory(self) -> None:
        if not isinstance(self.inventory, dict) or not self.inventory:
            return

        rx = re.compile(r"^(?:Syntax|Lexicon|Paradigms|All|Grammar)([A-Za-z]{3})$")
        for iso2, payload in self.inventory.items():
            if not (isinstance(iso2, str) and len(iso2.strip()) == 2):
                continue
            iso2c = iso2.strip().casefold()
            if iso2c in self.iso2_to_wiki:
                continue
            if not isinstance(payload, dict):
                continue
            mods = payload.get("modules")
            if not isinstance(mods, list):
                continue

            suffix = None
            for m in mods:
                if not isinstance(m, str):
                    continue
                hit = rx.match(m.strip())
                if hit:
                    suffix = hit.group(1)
                    break

            if suffix:
                self.iso2_to_wiki[iso2c] = suffix

    def _load_grammar_sync(self) -> None:
        with self._thread_load_lock:
            if self._grammar is not None:
                return

            self.last_load_error = None
            self.last_load_error_type = None

            if not pgf:
                self._grammar = None
                self.last_load_error_type = "pgf_missing"
                self.last_load_error = "Python module 'pgf' is not installed/available in this runtime."
                logger.error("pgf_module_missing")
                return

            path = Path(self.pgf_path)
            if path.exists() and path.is_dir():
                path = path / "semantik_architect.pgf"

            if not path.exists():
                self._grammar = None
                self.last_load_error_type = "pgf_file_missing"
                self.last_load_error = f"PGF file not found at: {path}"
                logger.error("pgf_file_missing", pgf_path=str(path))
                return

            try:
                logger.info("loading_pgf_binary", path=str(path))
                self._grammar = pgf.readPGF(str(path))
                logger.info(
                    "pgf_binary_loaded_successfully",
                    language_count=len(getattr(self._grammar, "languages", {}) or {}),
                )
            except Exception as exc:
                self._grammar = None
                self.last_load_error_type = "pgf_read_failed"
                self.last_load_error = f"pgf.readPGF failed: {exc}"
                logger.error("gf_load_failed", error=str(exc), pgf_path=str(path))

    async def _ensure_grammar(self) -> None:
        if self._grammar is not None:
            return
        async with self._async_load_lock:
            if self._grammar is None:
                await asyncio.to_thread(self._load_grammar_sync)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def status(self) -> Dict[str, Any]:
        await self._ensure_grammar()
        payload: Dict[str, Any] = {
            "loaded": self._grammar is not None,
            "backend": self.renderer_backend,
            "pgf_path": str(self.pgf_path),
            "error_type": self.last_load_error_type,
            "error": self.last_load_error,
        }
        if self._grammar is not None:
            payload["language_count"] = len(getattr(self._grammar, "languages", {}) or {})
        return payload

    async def realize(self, construction_plan: "ConstructionPlan | Mapping[str, Any] | Any") -> Any:
        """
        Authoritative Batch 6 renderer entrypoint.

        Contract:
            ConstructionPlan -> SurfaceResult

        Notes:
        - This method consumes planner/runtime-owned fields only.
        - It never mutates the input plan.
        - Legacy `generate(lang_code, frame)` remains available as a
          compatibility shim for older call sites.
        """
        construction_id = _clean_optional_str(_get_value(construction_plan, "construction_id"))
        lang_code = _clean_optional_str(_get_value(construction_plan, "lang_code"))

        if not construction_id:
            raise ValueError("construction_plan.construction_id is required")
        if not lang_code:
            raise ValueError("construction_plan.lang_code is required")

        slot_map = _as_dict(_get_value(construction_plan, "slot_map"))
        lexical_bindings = _as_dict(_get_value(construction_plan, "lexical_bindings"))
        generation_options = _as_dict(_get_value(construction_plan, "generation_options"))
        metadata = _as_dict(_get_value(construction_plan, "metadata"))

        if not lexical_bindings and isinstance(slot_map.get("lexical_bindings"), Mapping):
            lexical_bindings = _as_dict(slot_map.get("lexical_bindings"))

        effective_construction_id = self._effective_construction_id(
            construction_id=construction_id,
            metadata=metadata,
        )
        resolved_language = self._resolve_concrete_name(lang_code)

        backend_trace: list[str] = [
            "validated ConstructionPlan envelope",
            f"selected backend={self.renderer_backend}",
            f"effective_construction_id={effective_construction_id}",
        ]
        warnings: list[str] = []
        fallback_used = False
        ast_str: Optional[str] = None

        await self._ensure_grammar()

        if self._grammar is None:
            fallback_used = True
            warnings.append("GF runtime is not loaded")
            text = "<GF Runtime Not Loaded>"
            backend_trace.append("PGF unavailable")
            return self._build_realize_result(
                text=text,
                lang_code=lang_code,
                construction_id=construction_id,
                fallback_used=fallback_used,
                slot_map=slot_map,
                resolved_language=resolved_language,
                ast=ast_str,
                backend_trace=backend_trace,
                warnings=warnings,
                metadata=metadata,
            )

        if not resolved_language:
            fallback_used = True
            warnings.append(f"language {lang_code!r} is not available in the PGF binary")
            text = f"<Language '{lang_code}' not found>"
            backend_trace.append("language resolution failed")
            return self._build_realize_result(
                text=text,
                lang_code=lang_code,
                construction_id=construction_id,
                fallback_used=fallback_used,
                slot_map=slot_map,
                resolved_language=None,
                ast=ast_str,
                backend_trace=backend_trace,
                warnings=warnings,
                metadata=metadata,
            )

        try:
            ast_str = self._construction_plan_to_gf_ast(
                construction_id=construction_id,
                effective_construction_id=effective_construction_id,
                lang_code=lang_code,
                slot_map=slot_map,
                lexical_bindings=lexical_bindings,
                generation_options=generation_options,
                metadata=metadata,
            )
            backend_trace.append("constructed GF AST from ConstructionPlan")
        except ValueError as exc:
            fallback_used = True
            warnings.append(str(exc))
            text = f"<GF Unsupported Construction: {construction_id}>"
            backend_trace.append("construction not supported by GF adapter slice")
            return self._build_realize_result(
                text=text,
                lang_code=lang_code,
                construction_id=construction_id,
                fallback_used=fallback_used,
                slot_map=slot_map,
                resolved_language=resolved_language,
                ast=ast_str,
                backend_trace=backend_trace,
                warnings=warnings,
                metadata=metadata,
            )

        text = self.linearize(ast_str, lang_code)
        if self._is_placeholder_text(text):
            fallback_used = True
            warnings.append("GF linearization returned placeholder/error output")
            backend_trace.append("GF linearization returned placeholder")

            subject_name = self._extract_subject_name(slot_map)
            if subject_name:
                text = subject_name

        if not _clean_optional_str(text):
            fallback_used = True
            warnings.append("GF linearization produced empty output")
            backend_trace.append("empty linearization output")
            text = self._extract_subject_name(slot_map) or f"<GF could not realize {construction_id}>"

        return self._build_realize_result(
            text=text,
            lang_code=lang_code,
            construction_id=construction_id,
            fallback_used=fallback_used,
            slot_map=slot_map,
            resolved_language=resolved_language,
            ast=ast_str,
            backend_trace=backend_trace,
            warnings=warnings,
            metadata=metadata,
        )

    async def generate(self, lang_code: str, frame: Any) -> Sentence:
        """
        Legacy direct frame-to-GF path.

        Kept only as an explicit compatibility shim during the planner/runtime
        migration. New code should prefer `realize(construction_plan)`.
        """
        await self._ensure_grammar()

        if not self._grammar:
            dbg = {
                "renderer_backend": self.renderer_backend,
                "runtime_path": "legacy_direct_frame",
                "compatibility_shim": True,
                "pgf_path": str(self.pgf_path),
                "error_type": self.last_load_error_type,
                "error": self.last_load_error,
                "fallback_used": True,
            }
            return Sentence(text="<GF Runtime Not Loaded>", lang_code=lang_code, debug_info=dbg)

        if isinstance(frame, dict) and ("function" in frame or "args" in frame):
            ast_str = self._convert_to_gf_ast(frame, lang_code)
            text = self.linearize(ast_str, lang_code)
            if not text:
                text = "<LinearizeError>"

            return Sentence(
                text=text,
                lang_code=lang_code,
                debug_info={
                    "renderer_backend": self.renderer_backend,
                    "runtime_path": "legacy_direct_frame",
                    "compatibility_shim": True,
                    "fallback_used": self._is_placeholder_text(text),
                    "ast": ast_str,
                    "resolved_language": self._resolve_concrete_name(lang_code),
                },
            )

        bio = self._coerce_to_bio_frame(frame)
        ast_str = self._convert_to_gf_ast(bio, lang_code)
        text = self.linearize(ast_str, lang_code)

        fallback_used = False
        if not text or text.strip() in {"[]", ""}:
            fallback_used = True
            name = (bio.name or "").strip() or "<Unknown>"
            text = name

        return Sentence(
            text=text,
            lang_code=lang_code,
            debug_info={
                "renderer_backend": self.renderer_backend,
                "runtime_path": "legacy_direct_frame",
                "compatibility_shim": True,
                "fallback_used": fallback_used or self._is_placeholder_text(text),
                "ast": ast_str,
                "resolved_language": self._resolve_concrete_name(lang_code),
            },
        )

    def parse(self, sentence: str, language: str):
        g = self.grammar
        if not g:
            return []

        language_resolved = self._resolve_concrete_name(language)
        if not language_resolved:
            return []

        concrete_grammar = g.languages[language_resolved]
        try:
            return concrete_grammar.parse(sentence)
        except Exception:
            return []

    def linearize(self, expr: Any, language: str) -> str:
        g = self.grammar
        if not g:
            return "<GF Runtime Not Loaded>"

        language_resolved = self._resolve_concrete_name(language)
        if not language_resolved:
            return f"<Language '{language}' not found>"

        concrete_grammar = g.languages[language_resolved]

        if isinstance(expr, str):
            try:
                expr_obj = pgf.readExpr(expr) if pgf else expr
            except Exception as exc:
                return f"<LinearizeError: {exc}>"
        else:
            expr_obj = expr

        try:
            return concrete_grammar.linearize(expr_obj)
        except Exception as exc:
            return f"<LinearizeError: {exc}>"

    async def get_supported_languages(self) -> List[str]:
        await self._ensure_grammar()
        if not self._grammar:
            return []
        return list(self._grammar.languages.keys())

    async def reload(self) -> None:
        self._load_inventory()
        self._load_iso_config()
        self._derive_wiki_from_inventory()

        async with self._async_load_lock:
            with self._thread_load_lock:
                self._grammar = None
                self.last_load_error = None
                self.last_load_error_type = None

        await self._ensure_grammar()

    async def health_check(self) -> bool:
        await self._ensure_grammar()
        return self._grammar is not None

    def can_realize(self, construction_id: str, *, metadata: Mapping[str, Any] | None = None) -> bool:
        normalized = self._normalize_construction_id(construction_id)
        effective = self._effective_construction_id(
            construction_id=normalized,
            metadata=_as_dict(metadata),
        )
        return self._looks_like_bio_construction(effective) or self._looks_like_event_construction(effective)

    # ------------------------------------------------------------------
    # Batch 6 ConstructionPlan helpers
    # ------------------------------------------------------------------
    def _build_realize_result(
        self,
        *,
        text: str,
        lang_code: str,
        construction_id: str,
        fallback_used: bool,
        slot_map: Mapping[str, Any],
        resolved_language: Optional[str],
        ast: Optional[str],
        backend_trace: List[str],
        warnings: List[str],
        metadata: Mapping[str, Any],
    ) -> Any:
        debug_info: dict[str, Any] = {
            "construction_id": construction_id,
            "renderer_backend": self.renderer_backend,
            "lang_code": lang_code,
            "slot_keys": list(slot_map.keys()),
            "fallback_used": fallback_used,
            "backend_trace": list(backend_trace),
            "warnings": list(warnings),
            "pgf_path": str(self.pgf_path),
        }

        if resolved_language:
            debug_info["resolved_language"] = resolved_language
        if ast:
            debug_info["ast"] = ast
        if isinstance(metadata.get("base_construction_id"), str):
            debug_info["base_construction_id"] = metadata["base_construction_id"]
        if isinstance(metadata.get("wrapper_construction_id"), str):
            debug_info["wrapper_construction_id"] = metadata["wrapper_construction_id"]

        tokens = _normalize_tokens(text)
        return _build_surface_result(
            text=text,
            lang_code=lang_code,
            construction_id=construction_id,
            renderer_backend=self.renderer_backend,
            fallback_used=fallback_used,
            tokens=tokens,
            debug_info=debug_info,
        )

    def _normalize_construction_id(self, value: str) -> str:
        return value.strip().lower().replace("-", "_").replace(" ", "_")

    def _effective_construction_id(
        self,
        *,
        construction_id: str,
        metadata: Mapping[str, Any],
    ) -> str:
        base_id = _clean_optional_str(metadata.get("base_construction_id"))
        if base_id:
            return self._normalize_construction_id(base_id)
        return self._normalize_construction_id(construction_id)

    def _looks_like_bio_construction(self, construction_id: str) -> bool:
        cid = self._normalize_construction_id(construction_id)
        if cid in self._BIO_CONSTRUCTION_IDS:
            return True
        if "bio" in cid or "biography" in cid:
            return True
        if "equative" in cid or "classification" in cid:
            return True
        if "copular" in cid and "event" not in cid:
            return True
        return False

    def _looks_like_event_construction(self, construction_id: str) -> bool:
        cid = self._normalize_construction_id(construction_id)
        if cid in self._EVENT_CONSTRUCTION_IDS:
            return True
        return "event" in cid

    def _construction_plan_to_gf_ast(
        self,
        *,
        construction_id: str,
        effective_construction_id: str,
        lang_code: str,
        slot_map: Mapping[str, Any],
        lexical_bindings: Mapping[str, Any],
        generation_options: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> str:
        if self._looks_like_bio_construction(effective_construction_id):
            bio = self._bio_frame_from_construction_plan(
                construction_id=construction_id,
                slot_map=slot_map,
                lexical_bindings=lexical_bindings,
                generation_options=generation_options,
                metadata=metadata,
            )
            return self._convert_to_gf_ast(bio, lang_code)

        if self._looks_like_event_construction(effective_construction_id):
            return self._event_ast_from_construction_plan(
                slot_map=slot_map,
                lexical_bindings=lexical_bindings,
            )

        raise ValueError(f"unsupported GF construction_id {construction_id!r}")

    def _bio_frame_from_construction_plan(
        self,
        *,
        construction_id: str,
        slot_map: Mapping[str, Any],
        lexical_bindings: Mapping[str, Any],
        generation_options: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> BioFrame:
        name = self._extract_subject_name(slot_map)
        if not name:
            raise ValueError(f"{construction_id!r} requires a non-empty subject label/name")

        profession = self._extract_profession(slot_map, lexical_bindings)
        nationality = self._extract_nationality(slot_map, lexical_bindings)
        gender = self._extract_gender(slot_map, lexical_bindings)

        return BioFrame(
            frame_type="bio",
            subject={
                "name": name,
                "profession": profession,
                "nationality": nationality,
                "gender": gender,
            },
            context_id="",
            meta={
                "source": "construction_plan",
                "construction_id": construction_id,
                "generation_options": dict(generation_options),
                "metadata": dict(metadata),
            },
        )

    def _event_ast_from_construction_plan(
        self,
        *,
        slot_map: Mapping[str, Any],
        lexical_bindings: Mapping[str, Any],
    ) -> str:
        subject_name = self._extract_subject_name(slot_map)
        if not subject_name:
            raise ValueError("event construction requires a subject/topic/agent label")

        event_label = self._extract_event_label(slot_map, lexical_bindings)
        if not event_label:
            raise ValueError("event construction requires an event/predicate label or lexical binding")

        subj_esc = self._escape_gf_str(subject_name)
        event_esc = self._escape_gf_str(event_label)
        return f'mkEvent (mkEntityStr "{subj_esc}") (strEvent "{event_esc}")'

    def _extract_subject_name(self, slot_map: Mapping[str, Any]) -> Optional[str]:
        for key in self._SUBJECT_SLOT_KEYS:
            value = slot_map.get(key)
            text = self._extract_text(value)
            if text:
                return text

        for value in slot_map.values():
            if isinstance(value, Mapping) and any(k in value for k in ("name", "label", "title")):
                text = self._extract_text(value)
                if text:
                    return text
        return None

    def _extract_profession(
        self,
        slot_map: Mapping[str, Any],
        lexical_bindings: Mapping[str, Any],
    ) -> Optional[str]:
        for key in ("profession", "occupation", "predicate_nominal"):
            text = self._extract_lexical_value(lexical_bindings.get(key))
            if text:
                return text

        for key in self._PROF_SLOT_KEYS:
            value = slot_map.get(key)
            text = self._extract_slot_lexeme(value, nested_keys=("profession", "occupation"))
            if text:
                return text
        return None

    def _extract_nationality(
        self,
        slot_map: Mapping[str, Any],
        lexical_bindings: Mapping[str, Any],
    ) -> Optional[str]:
        for key in ("nationality", "citizenship", "predicate_nominal"):
            text = self._extract_lexical_value(lexical_bindings.get(key))
            if text:
                return text

        for key in self._NAT_SLOT_KEYS:
            value = slot_map.get(key)
            text = self._extract_slot_lexeme(value, nested_keys=("nationality", "citizenship"))
            if text:
                return text
        return None

    def _extract_event_label(
        self,
        slot_map: Mapping[str, Any],
        lexical_bindings: Mapping[str, Any],
    ) -> Optional[str]:
        for key in ("event", "predicate", "event_obj", "verb"):
            text = self._extract_lexical_value(lexical_bindings.get(key))
            if text:
                return text

        for key in self._EVENT_SLOT_KEYS:
            value = slot_map.get(key)
            text = self._extract_slot_lexeme(value, nested_keys=("event", "predicate", "label", "name"))
            if text:
                return text
        return None

    def _extract_gender(
        self,
        slot_map: Mapping[str, Any],
        lexical_bindings: Mapping[str, Any],
    ) -> Optional[str]:
        subject = slot_map.get("subject")
        gender = None
        if isinstance(subject, Mapping):
            gender = subject.get("gender")
            if gender is None and isinstance(subject.get("features"), Mapping):
                gender = subject["features"].get("gender")

        if gender is None:
            gender = lexical_bindings.get("gender")

        return self._normalize_gender(gender)

    def _extract_slot_lexeme(self, value: Any, *, nested_keys: tuple[str, ...]) -> Optional[str]:
        if isinstance(value, Mapping):
            for nested in nested_keys:
                inner = value.get(nested)
                text = self._extract_lexical_value(inner)
                if text:
                    return text
            return self._extract_lexical_value(value)
        return self._extract_lexical_value(value)

    def _extract_lexical_value(self, value: Any) -> Optional[str]:
        if value is None:
            return None

        if isinstance(value, str):
            return _clean_optional_str(value)

        if isinstance(value, Mapping):
            for key in ("lemma", "label", "name", "title", "text", "value"):
                text = _clean_optional_str(value.get(key))
                if text:
                    return text

        return self._extract_text(value)

    def _extract_text(self, value: Any) -> Optional[str]:
        if value is None:
            return None

        if isinstance(value, str):
            return _clean_optional_str(value)

        if isinstance(value, Mapping):
            for key in ("label", "name", "title", "text", "lemma", "value"):
                text = _clean_optional_str(value.get(key))
                if text:
                    return text

            for key in ("subject", "entity", "main_entity", "person"):
                nested = value.get(key)
                text = self._extract_text(nested)
                if text:
                    return text

        for attr in ("label", "name", "title", "text", "lemma", "value"):
            text = _clean_optional_str(getattr(value, attr, None))
            if text:
                return text

        return None

    def _is_placeholder_text(self, text: str) -> bool:
        out = (text or "").strip()
        if not out:
            return True
        if out in {"[]", "<LinearizeError>", "<GF Runtime Not Loaded>"}:
            return True
        if out.startswith("<LinearizeError"):
            return True
        if out.startswith("<Language '") and out.endswith(">"):
            return True
        if out.startswith("<GF ") and out.endswith(">"):
            return True
        return False

    # ------------------------------------------------------------------
    # Language resolution
    # ------------------------------------------------------------------
    def _norm_to_iso2(self, code: str) -> Optional[str]:
        if not isinstance(code, str):
            return None
        k = code.strip().casefold()
        if not k:
            return None
        if k.startswith("wiki") and len(k) > 4:
            k = k[4:]

        hit = self.wiki_to_iso2.get(k)
        if isinstance(hit, str) and len(hit) == 2:
            return hit

        if len(k) == 2 and k.isalpha():
            return k

        return None

    def _resolve_concrete_name(self, lang_code: str) -> Optional[str]:
        g = self._grammar
        if not g:
            return None

        raw = (lang_code or "").strip()
        if not raw:
            return None

        if raw in g.languages:
            return raw

        lower_to_key = {k.lower(): k for k in g.languages.keys()}
        rl = raw.lower()
        if rl in lower_to_key:
            return lower_to_key[rl]

        def _try_candidates(cands: List[str]) -> Optional[str]:
            for c in cands:
                if not c:
                    continue
                if c in g.languages:
                    return c
                cl = c.lower()
                if cl in lower_to_key:
                    return lower_to_key[cl]
            return None

        iso2 = self._norm_to_iso2(raw)
        iso3 = self.iso2_to_iso3.get(iso2) if iso2 else None
        wiki = self.iso2_to_wiki.get(iso2) if iso2 else None

        candidates: List[str] = []

        if wiki:
            s = wiki.strip()
            candidates.extend(
                [
                    f"Wiki{s}",
                    f"Wiki{s.capitalize()}",
                    f"Wiki{s.upper()}",
                    s,
                    s.capitalize(),
                    s.upper(),
                    s.lower(),
                ]
            )

        if iso3:
            s3 = iso3.strip()
            candidates.extend(
                [
                    f"Wiki{s3.capitalize()}",
                    f"Wiki{s3.upper()}",
                    s3,
                    s3.upper(),
                    s3.lower(),
                ]
            )

        if iso2:
            candidates.extend([f"Wiki{iso2.upper()}", f"Wiki{iso2.capitalize()}", iso2])

        hit = _try_candidates(candidates)
        if hit:
            return hit

        probes: List[str] = []
        if wiki:
            probes.append(wiki.casefold())
        if iso3:
            probes.append(iso3.casefold())
        if iso2:
            probes.append(iso2.casefold())

        for probe in probes:
            for k in g.languages.keys():
                kl = k.casefold()
                if kl == probe or kl == f"wiki{probe}":
                    return k
                if kl.endswith(probe) or kl.endswith(f"wiki{probe}"):
                    return k

        return None

    # ------------------------------------------------------------------
    # Legacy payload helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _escape_gf_str(s: str) -> str:
        return (s or "").replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _pick(self, source: Dict[str, Any], keys: tuple[str, ...]) -> Optional[str]:
        for key in keys:
            val = _clean_optional_str(source.get(key))
            if val:
                return val
        return None

    def _normalize_gender(self, value: Any) -> Optional[str]:
        s = _clean_optional_str(value)
        if not s:
            return None

        sl = s.lower()
        if sl in {"male", "man", "masculine"}:
            return "m"
        if sl in {"female", "woman", "feminine"}:
            return "f"
        if sl in {"neuter"}:
            return "n"
        if sl in {"m", "f", "n"}:
            return sl
        return s

    def _subject_from_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        subject = self._as_dict(payload.get("subject"))
        main_entity = self._as_dict(payload.get("main_entity"))
        props = self._as_dict(payload.get("properties"))

        merged: Dict[str, Any] = {}
        merged.update(subject)
        merged.update(main_entity)

        name = self._pick(payload, self._NAME_KEYS) or self._pick(props, self._NAME_KEYS)
        profession = self._pick(payload, self._PROF_KEYS) or self._pick(props, self._PROF_KEYS)
        nationality = self._pick(payload, self._NAT_KEYS) or self._pick(props, self._NAT_KEYS)
        gender = self._normalize_gender(self._pick(payload, self._GENDER_KEYS) or self._pick(props, self._GENDER_KEYS))
        qid = self._pick(payload, self._QID_KEYS) or self._pick(props, self._QID_KEYS)

        if not self._pick(merged, self._NAME_KEYS):
            fallback_name = self._pick(main_entity, self._NAME_KEYS) or self._pick(subject, self._NAME_KEYS)
            if fallback_name:
                merged["name"] = fallback_name
        if name:
            merged["name"] = name

        if not self._pick(merged, self._PROF_KEYS):
            fallback_prof = self._pick(main_entity, self._PROF_KEYS) or self._pick(subject, self._PROF_KEYS)
            if fallback_prof:
                merged["profession"] = fallback_prof
        if profession:
            merged["profession"] = profession

        if not self._pick(merged, self._NAT_KEYS):
            fallback_nat = self._pick(main_entity, self._NAT_KEYS) or self._pick(subject, self._NAT_KEYS)
            if fallback_nat:
                merged["nationality"] = fallback_nat
        if nationality:
            merged["nationality"] = nationality

        if not self._pick(merged, self._GENDER_KEYS):
            fallback_gender = self._normalize_gender(
                self._pick(main_entity, self._GENDER_KEYS) or self._pick(subject, self._GENDER_KEYS)
            )
            if fallback_gender:
                merged["gender"] = fallback_gender
        if gender:
            merged["gender"] = gender

        if not self._pick(merged, self._QID_KEYS):
            fallback_qid = self._pick(main_entity, self._QID_KEYS) or self._pick(subject, self._QID_KEYS)
            if fallback_qid:
                merged["qid"] = fallback_qid
        if qid:
            merged["qid"] = qid

        return merged

    def _is_bio_like_payload(self, payload: Dict[str, Any]) -> bool:
        frame_type_raw = payload.get("frame_type") or payload.get("type") or ""
        frame_type = str(frame_type_raw).lower().strip() if frame_type_raw is not None else ""

        if frame_type in self._BIO_FRAME_TYPES:
            return True
        if frame_type.startswith("entity.") and "person" in frame_type:
            return True

        merged = self._subject_from_payload(payload)
        return bool(
            self._pick(merged, self._NAME_KEYS)
            or self._pick(merged, self._PROF_KEYS)
            or self._pick(merged, self._NAT_KEYS)
            or self._pick(merged, self._GENDER_KEYS)
        )

    def _coerce_to_bio_frame(self, obj: Any) -> BioFrame:
        if isinstance(obj, BioFrame):
            return obj

        if isinstance(obj, Frame):
            payload: Dict[str, Any] = {
                "frame_type": getattr(obj, "frame_type", "bio") or "bio",
                "subject": dict(getattr(obj, "subject", {}) or {}),
                "properties": dict(getattr(obj, "properties", {}) or {}),
                "meta": dict(getattr(obj, "meta", {}) or {}),
                "context_id": getattr(obj, "context_id", "") or "",
            }
            subject = self._subject_from_payload(payload)
            return BioFrame(
                frame_type="bio",
                subject=subject,
                context_id=payload["context_id"] or "",
                meta=payload["meta"] or {},
            )

        if isinstance(obj, dict):
            if not self._is_bio_like_payload(obj):
                raise ValueError("Unsupported frame payload for Bio generation")

            subject = self._subject_from_payload(obj)
            return BioFrame(
                frame_type="bio",
                subject=subject,
                context_id=obj.get("context_id") or "",
                meta=obj.get("meta") or {},
            )

        raise ValueError("Unsupported frame payload for Bio generation")

    def _bio_fields(self, frame: BioFrame) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
        name = _clean_optional_str(getattr(frame, "name", None)) or ""
        gender = self._normalize_gender(getattr(frame, "gender", None))

        profession: Optional[str] = None
        nationality: Optional[str] = None

        subj = getattr(frame, "subject", None)
        if isinstance(subj, dict):
            profession = self._pick(subj, self._PROF_KEYS)
            nationality = self._pick(subj, self._NAT_KEYS)

            if not name:
                name = self._pick(subj, self._NAME_KEYS) or ""
            if gender is None:
                gender = self._normalize_gender(self._pick(subj, self._GENDER_KEYS))
        else:
            profession = _clean_optional_str(getattr(subj, "profession", None))
            nationality = _clean_optional_str(getattr(subj, "nationality", None))

            if not name:
                name = _clean_optional_str(getattr(subj, "name", None)) or ""
            if gender is None:
                gender = self._normalize_gender(getattr(subj, "gender", None))

        return name, profession, nationality, gender

    def _convert_to_gf_ast(self, node: Any, lang_code: str) -> str:
        if isinstance(node, BioFrame):
            name, prof, nat, _gender = self._bio_fields(node)

            name_esc = self._escape_gf_str(name or "Unknown")
            prof_esc = self._escape_gf_str(prof or "")
            nat_esc = self._escape_gf_str(nat or "")

            entity = f'mkEntityStr "{name_esc}"'

            if prof_esc and nat_esc:
                prof_expr = f'strProf "{prof_esc}"'
                nat_expr = f'strNat "{nat_esc}"'
                return f"mkBioFull ({entity}) ({prof_expr}) ({nat_expr})"

            if nat_esc:
                nat_expr = f'strNat "{nat_esc}"'
                return f"mkBioNat ({entity}) ({nat_expr})"

            prof_default = self._escape_gf_str(prof or "person")
            prof_expr = f'strProf "{prof_default}"'
            return f"mkBioProf ({entity}) ({prof_expr})"

        if isinstance(node, dict):
            func = node.get("function")
            if not func:
                raise ValueError("Missing function attribute")

            args = node.get("args", [])
            processed = [self._convert_to_gf_ast(a, lang_code) for a in (args or [])]

            def needs_parens(expr: str) -> bool:
                expr = (expr or "").strip()
                if not expr:
                    return False
                if expr.startswith('"') and expr.endswith('"'):
                    return False
                if " " in expr or expr.startswith("("):
                    return True
                return False

            arg_str = " ".join([f"({a})" if needs_parens(a) else a for a in processed]).strip()
            candidate = f"{func} {arg_str}".strip()

            if func == "mkCl" and self._linearizes_as_placeholder(candidate, lang_code):
                return self._flatten_ninai_to_literal(node)

            return candidate

        if isinstance(node, str):
            return f'"{self._escape_gf_str(node)}"'
        if node is None:
            return '""'
        return f'"{self._escape_gf_str(str(node))}"'

    def _linearizes_as_placeholder(self, expr_str: str, lang_code: str) -> bool:
        if not (self._grammar and pgf):
            return False

        conc_name = self._resolve_concrete_name(lang_code)
        if not conc_name or conc_name not in self._grammar.languages:
            return False

        try:
            expr_obj = pgf.readExpr(expr_str)
            out = self._grammar.languages[conc_name].linearize(expr_obj)
        except Exception:
            return True

        out_s = (out or "").strip()
        return (out_s.startswith("[") and out_s.endswith("]")) or ("[mkCl]" in out_s)

    def _flatten_ninai_to_literal(self, node: Any) -> str:
        tokens: list[str] = []

        def walk(n: Any) -> None:
            if isinstance(n, dict):
                fn = n.get("function")
                if isinstance(fn, str) and fn:
                    tokens.append(fn)
                for a in (n.get("args") or []):
                    walk(a)
            elif isinstance(n, str):
                if n:
                    tokens.append(n)
            else:
                if n is not None:
                    tokens.append(str(n))

        walk(node)
        joined = " ".join(tokens).strip() or "unsupported"
        return f'"{self._escape_gf_str(joined)}"'