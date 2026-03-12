# app/adapters/engines/gf_engine.py
from __future__ import annotations

import json
import os
from collections.abc import Mapping as ABCMapping
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import structlog

try:
    import pgf  # type: ignore
except Exception:  # pragma: no cover
    pgf = None  # type: ignore

from app.core.domain.exceptions import (
    DomainError,
    GrammarCompilationError,
    LanguageNotFoundError,
    UnsupportedFrameTypeError,
)
from app.core.domain.frame import BioFrame
from app.core.domain.models import Frame, Sentence
from app.core.ports.grammar_engine import IGrammarEngine
from app.shared.config import settings

try:  # Runtime-safe during staged migration.
    from app.core.domain.planning.construction_plan import ConstructionPlan
except Exception:  # pragma: no cover
    ConstructionPlan = Any  # type: ignore[assignment,misc]

logger = structlog.get_logger()

GF_DEFAULT_BINARY = "semantik_architect.pgf"

_BIO_FRAME_TYPES = frozenset(
    {
        "bio",
        "biography",
        "entity.person",
        "entity_person",
        "person",
        "entity.person.v1",
        "entity.person.v2",
    }
)

_SUPPORTED_CONSTRUCTION_IDS = frozenset(
    {
        "bio",
        "biography",
        "copula_equative_simple",
        "copula_equative_classification",
        "copula_equative_profession_nationality",
        "copula_equative_bio",
        "copula_equative_bio_simple",
    }
)


class GFUnsupportedConstructionError(DomainError):
    def __init__(self, construction_id: str):
        super().__init__(
            f"GF backend does not support construction '{construction_id}'."
        )


class UnlexicalizedPlanError(DomainError):
    def __init__(self, message: str):
        super().__init__(message)


def _normalize_pgf_path(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return value
    if value.endswith(("/", "\\")) or not value.lower().endswith(".pgf"):
        return os.path.join(value, GF_DEFAULT_BINARY)
    return value


def _effective_pgf_path() -> str:
    env_path = os.getenv("PGF_PATH") or os.getenv("AW_PGF_PATH")
    if env_path:
        return _normalize_pgf_path(env_path)
    return _normalize_pgf_path(getattr(settings, "PGF_PATH", "") or "")


def _repo_root() -> Path:
    for attr in ("REPO_ROOT", "ROOT_DIR", "PROJECT_ROOT", "FILESYSTEM_REPO_PATH"):
        val = getattr(settings, attr, None)
        if val:
            return Path(val).resolve()
    return Path(__file__).resolve().parents[3]


def _load_iso_to_wiki_map() -> Dict[str, Any]:
    root = _repo_root()
    candidates = [
        root / "data" / "config" / "iso_to_wiki.json",
        root / "gf" / "data" / "config" / "iso_to_wiki.json",
        root / "config" / "iso_to_wiki.json",
    ]

    for path in candidates:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    logger.info("iso_map_loaded", path=str(path), entries=len(data))
                    return data
        except Exception as exc:
            logger.warning("iso_map_load_failed", path=str(path), error=str(exc))

    logger.warning("iso_map_missing", tried=[str(p) for p in candidates])
    return {}


def _extract_wiki_suffix(raw_val: Any) -> Optional[str]:
    if raw_val is None:
        return None
    if isinstance(raw_val, ABCMapping):
        raw_val = raw_val.get("wiki")
    if raw_val is None:
        return None
    s = str(raw_val).strip()
    if not s:
        return None
    return s.replace("Wiki", "").strip() or None


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _escape_gf_string(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace('"', '\\"')


def _mapping_get_str(data: Any, key: str) -> Optional[str]:
    if isinstance(data, ABCMapping):
        return _safe_str(data.get(key))
    return None


def _get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, ABCMapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_mapping(obj: Any, key: str) -> Mapping[str, Any]:
    value = _get_value(obj, key, {})
    if isinstance(value, ABCMapping):
        return value
    return {}


def _coerce_non_empty_str(value: Any, *, field_name: str) -> str:
    text = _safe_str(value)
    if not text:
        raise DomainError(f"{field_name} must be a non-empty string.")
    return text


class GFEngine(IGrammarEngine):
    """
    GF-backed renderer.

    Canonical path:
        ConstructionPlan -> realize() -> Sentence

    Compatibility path:
        Frame -> generate() -> ConstructionPlan shim -> realize()

    Current realization slice:
    - bio / equative classification plans
    - subject + profession and/or nationality
    """

    backend_name = "gf"

    def __init__(self) -> None:
        self._iso_map: Dict[str, Any] = _load_iso_to_wiki_map()
        self._wiki_to_iso2: Dict[str, str] = {}

        for key, value in self._iso_map.items():
            suffix = _extract_wiki_suffix(value)
            if suffix:
                iso2 = str(key).strip().lower()
                self._wiki_to_iso2[suffix] = iso2
                self._wiki_to_iso2[suffix.lower()] = iso2

        self._pgf = self._load_pgf()
        self._supported_gf_langs = self._get_supported_gf_langs()
        self._supported_languages = self._compute_supported_languages()

    # ------------------------------------------------------------------
    # Lifecycle / capability
    # ------------------------------------------------------------------

    def _load_pgf(self) -> Any:
        pgf_file = _effective_pgf_path()

        if pgf is None:
            logger.error("pgf_module_missing")
            return None

        if not pgf_file or not os.path.exists(pgf_file):
            logger.error("pgf_file_missing", path=pgf_file or "(empty)")
            return None

        try:
            grammar = pgf.readPGF(pgf_file)
            logger.info("pgf_loaded", path=pgf_file, languages=len(grammar.languages))
            return grammar
        except Exception as exc:
            logger.error("pgf_load_failed", path=pgf_file, error=str(exc))
            return None

    def _get_supported_gf_langs(self) -> set[str]:
        if self._pgf is None:
            return set()
        return set(getattr(self._pgf, "languages", {}).keys())

    def _compute_supported_languages(self) -> set[str]:
        out: set[str] = set()
        for name in self._supported_gf_langs:
            suffix = str(name).replace("Wiki", "").strip()
            if not suffix:
                continue
            iso2 = self._wiki_to_iso2.get(suffix) or self._wiki_to_iso2.get(suffix.lower())
            out.add((iso2 or suffix).lower())
        return out

    async def reload(self) -> None:
        self._iso_map = _load_iso_to_wiki_map()
        self._wiki_to_iso2 = {}
        for key, value in self._iso_map.items():
            suffix = _extract_wiki_suffix(value)
            if suffix:
                iso2 = str(key).strip().lower()
                self._wiki_to_iso2[suffix] = iso2
                self._wiki_to_iso2[suffix.lower()] = iso2

        self._pgf = self._load_pgf()
        self._supported_gf_langs = self._get_supported_gf_langs()
        self._supported_languages = self._compute_supported_languages()

    async def get_supported_languages(self) -> list[str]:
        return sorted(self._supported_languages)

    async def health_check(self) -> bool:
        is_ready = self._pgf is not None and bool(self._supported_gf_langs)
        if not is_ready:
            logger.warning(
                "gf_health_check_failed",
                reason="PGF not loaded or no concrete syntaxes found",
            )
        return is_ready

    def supports(self, construction_id: str, lang_code: str) -> bool:
        return self._supports_construction_id(construction_id) and self.is_language_ready(
            lang_code
        )

    def get_support_status(self, construction_id: str, lang_code: str) -> str:
        return "full" if self.supports(construction_id, lang_code) else "unsupported"

    def _supports_construction_id(self, construction_id: str) -> bool:
        cid = (construction_id or "").strip().lower()
        if not cid:
            return False
        if cid in _SUPPORTED_CONSTRUCTION_IDS:
            return True
        return "bio" in cid or ("equative" in cid and "copula" in cid)

    # ------------------------------------------------------------------
    # Language resolution
    # ------------------------------------------------------------------

    def _gf_lang_name(self, lang_code: str) -> str:
        code = (lang_code or "").strip()
        if not code:
            return "WikiUnknown"

        if code.startswith("Wiki") and len(code) > 4:
            return code

        raw_val = self._iso_map.get(code) or self._iso_map.get(code.lower())
        suffix = _extract_wiki_suffix(raw_val)

        if not suffix:
            stripped = code.replace("Wiki", "").strip()
            if len(stripped) == 2:
                suffix = stripped.upper()
            else:
                suffix = stripped[:1].upper() + stripped[1:]

        return f"Wiki{suffix}"

    def _resolve_loaded_gf_lang_name(self, lang_code: str) -> Optional[str]:
        if self._pgf is None:
            return None

        candidate = self._gf_lang_name(lang_code)
        if candidate in self._pgf.languages:
            return candidate

        lower_to_actual = {k.lower(): k for k in self._pgf.languages.keys()}
        if candidate.lower() in lower_to_actual:
            return lower_to_actual[candidate.lower()]

        raw = (lang_code or "").strip()
        if raw in self._pgf.languages:
            return raw
        if raw.lower() in lower_to_actual:
            return lower_to_actual[raw.lower()]

        suffix = raw.replace("Wiki", "").strip().lower()
        for concrete in self._pgf.languages.keys():
            concrete_lc = concrete.lower()
            if concrete_lc == f"wiki{suffix}" or concrete_lc.endswith(suffix):
                return concrete

        return None

    def is_language_ready(self, lang_code: str) -> bool:
        return self._resolve_loaded_gf_lang_name(lang_code) is not None

    # ------------------------------------------------------------------
    # Canonical realization path
    # ------------------------------------------------------------------

    async def realize(self, construction_plan: ConstructionPlan) -> Sentence:
        construction_id = _coerce_non_empty_str(
            _get_value(construction_plan, "construction_id"),
            field_name="construction_id",
        )
        lang_code = _coerce_non_empty_str(
            _get_value(construction_plan, "lang_code"),
            field_name="lang_code",
        ).lower()

        if self._pgf is None:
            raise GrammarCompilationError(
                lang_code,
                "GF engine is not initialized. PGF file is missing, unreadable, or pgf is unavailable.",
            )

        if not self._supports_construction_id(construction_id):
            raise GFUnsupportedConstructionError(construction_id)

        gf_lang_name = self._resolve_loaded_gf_lang_name(lang_code)
        if not gf_lang_name:
            raise LanguageNotFoundError(lang_code)

        ast_string, render_meta = self._map_construction_plan_to_ast(construction_plan)

        try:
            ast_expr = pgf.readExpr(ast_string) if pgf is not None else ast_string
        except Exception as exc:
            logger.error(
                "gf_ast_parse_failed",
                construction_id=construction_id,
                lang_code=lang_code,
                ast=ast_string,
                error=str(exc),
            )
            raise GrammarCompilationError(lang_code, f"Failed to parse AST: {exc}") from exc

        try:
            concrete = self._pgf.languages[gf_lang_name]
            text = str(concrete.linearize(ast_expr)).strip()
        except Exception as exc:
            logger.error(
                "gf_linearization_failed",
                construction_id=construction_id,
                lang_code=lang_code,
                resolved_language=gf_lang_name,
                ast=ast_string,
                error=str(exc),
            )
            raise GrammarCompilationError(
                lang_code,
                f"GF linearization failed for concrete '{gf_lang_name}': {exc}",
            ) from exc

        if not text:
            raise GrammarCompilationError(lang_code, "GF returned empty surface text.")

        debug_info: dict[str, Any] = {
            "construction_id": construction_id,
            "renderer_backend": self.backend_name,
            "lang_code": lang_code,
            "resolved_language": gf_lang_name,
            "fallback_used": bool(render_meta["fallback_used"]),
            "slot_keys": list(render_meta["slot_keys"]),
            "ast": ast_string,
            "backend_trace": [
                "validated ConstructionPlan",
                "mapped plan to GF AST",
                f"linearized via {gf_lang_name}",
            ],
        }

        warnings = render_meta.get("warnings") or []
        if warnings:
            debug_info["warnings"] = list(warnings)

        lexical_resolution = render_meta.get("lexical_resolution")
        if isinstance(lexical_resolution, ABCMapping) and lexical_resolution:
            debug_info["lexical_resolution"] = dict(lexical_resolution)

        return Sentence(
            text=text,
            lang_code=lang_code,
            construction_id=construction_id,
            renderer_backend=self.backend_name,
            fallback_used=bool(render_meta["fallback_used"]),
            tokens=[part for part in text.split() if part],
            debug_info=debug_info,
        )

    # ------------------------------------------------------------------
    # Legacy compatibility path
    # ------------------------------------------------------------------

    async def generate(self, lang_code: str, frame: Frame | Mapping[str, Any]) -> Sentence:
        plan = self._frame_to_construction_plan(lang_code=lang_code, frame=frame)
        realized = await self.realize(plan)

        debug_info = dict(realized.debug_info or {})
        trace = debug_info.get("backend_trace")
        if isinstance(trace, list):
            trace = list(trace)
        else:
            trace = []
        trace.insert(0, "legacy generate() compatibility shim")
        debug_info["backend_trace"] = trace
        debug_info["compatibility_mode"] = "frame_to_plan_to_realize"

        return Sentence(
            text=realized.text,
            lang_code=realized.lang_code,
            construction_id=realized.construction_id,
            renderer_backend=realized.renderer_backend,
            fallback_used=realized.fallback_used,
            tokens=list(realized.tokens),
            debug_info=debug_info,
            generation_time_ms=realized.generation_time_ms,
        )

    def _frame_to_construction_plan(
        self,
        *,
        lang_code: str,
        frame: Frame | Mapping[str, Any],
    ) -> Any:
        frame_type = self._frame_type(frame)
        if frame_type not in _BIO_FRAME_TYPES:
            raise UnsupportedFrameTypeError(frame_type or type(frame).__name__)

        name, profession, nationality = self._extract_bio_fields(frame)

        slot_map: dict[str, Any] = {
            "subject": {
                "label": name,
                "name": name,
                "entity_type": "person",
            }
        }

        lexical_bindings: dict[str, Any] = {}

        if profession:
            slot_map["profession"] = profession
            lexical_bindings["profession"] = {
                "lemma": profession,
                "source": "legacy_frame",
            }

        if nationality:
            slot_map["nationality"] = nationality
            lexical_bindings["nationality"] = {
                "lemma": nationality,
                "source": "legacy_frame",
            }

        payload: dict[str, Any] = {
            "construction_id": (
                "copula_equative_classification"
                if nationality
                else "copula_equative_simple"
            ),
            "lang_code": (lang_code or "").strip().lower(),
            "slot_map": slot_map,
            "generation_options": {
                "allow_fallback": True,
            },
            "focus_role": "predicate_nominal",
            "lexical_bindings": lexical_bindings,
        }

        try:
            return ConstructionPlan(**payload)  # type: ignore[misc,call-arg]
        except Exception:
            return payload

    # ------------------------------------------------------------------
    # Construction-plan -> GF AST
    # ------------------------------------------------------------------

    def _map_construction_plan_to_ast(
        self,
        construction_plan: Any,
    ) -> tuple[str, dict[str, Any]]:
        construction_id = _coerce_non_empty_str(
            _get_value(construction_plan, "construction_id"),
            field_name="construction_id",
        )
        if not self._supports_construction_id(construction_id):
            raise GFUnsupportedConstructionError(construction_id)

        slot_map = _get_mapping(construction_plan, "slot_map")
        lexical_bindings = _get_mapping(construction_plan, "lexical_bindings")
        generation_options = _get_mapping(construction_plan, "generation_options")

        subject_name = self._extract_subject_name(slot_map)
        if not subject_name:
            raise UnlexicalizedPlanError(
                "ConstructionPlan is missing a usable subject label/name."
            )

        profession = self._extract_bio_slot_value(
            slot_map=slot_map,
            lexical_bindings=lexical_bindings,
            slot_name="profession",
        )
        nationality = self._extract_bio_slot_value(
            slot_map=slot_map,
            lexical_bindings=lexical_bindings,
            slot_name="nationality",
        )

        # predicate_nominal may carry profession/nationality-like payloads in some plans.
        predicate_nominal = slot_map.get("predicate_nominal")
        if isinstance(predicate_nominal, ABCMapping):
            profession = profession or _mapping_get_str(predicate_nominal, "profession")
            nationality = nationality or _mapping_get_str(predicate_nominal, "nationality")

        allow_fallback = bool(generation_options.get("allow_fallback", False))
        fallback_used = False
        warnings: list[str] = []

        entity_expr = f'mkEntityStr "{_escape_gf_string(subject_name)}"'

        if profession and nationality:
            prof_expr = f'strProf "{_escape_gf_string(profession)}"'
            nat_expr = f'strNat "{_escape_gf_string(nationality)}"'
            ast = f"mkBioFull ({entity_expr}) ({prof_expr}) ({nat_expr})"
        elif profession:
            prof_expr = f'strProf "{_escape_gf_string(profession)}"'
            ast = f"mkBioProf ({entity_expr}) ({prof_expr})"
        elif nationality:
            nat_expr = f'strNat "{_escape_gf_string(nationality)}"'
            ast = f"mkBioNat ({entity_expr}) ({nat_expr})"
        else:
            if not allow_fallback:
                raise UnlexicalizedPlanError(
                    "ConstructionPlan lacks profession/nationality and allow_fallback is false."
                )
            fallback_used = True
            warnings.append("gf_default_profession_fallback")
            ast = f'mkBioProf ({entity_expr}) (strProf "person")'

        lexical_resolution: dict[str, Any] = {}
        if profession:
            lexical_resolution["profession"] = {
                "value": profession,
                "source": self._binding_source(lexical_bindings.get("profession")),
            }
        if nationality:
            lexical_resolution["nationality"] = {
                "value": nationality,
                "source": self._binding_source(lexical_bindings.get("nationality")),
            }

        return ast, {
            "fallback_used": fallback_used,
            "warnings": warnings,
            "slot_keys": sorted(str(k) for k in slot_map.keys()),
            "lexical_resolution": lexical_resolution,
        }

    def _binding_source(self, value: Any) -> str:
        if isinstance(value, ABCMapping):
            src = _safe_str(value.get("source"))
            if src:
                return src
        return "plan"

    def _extract_subject_name(self, slot_map: Mapping[str, Any]) -> Optional[str]:
        subject = slot_map.get("subject")
        if isinstance(subject, ABCMapping):
            for key in ("label", "name", "title", "surface", "text", "value"):
                value = _mapping_get_str(subject, key)
                if value:
                    return value
        return _safe_str(subject)

    def _extract_bio_slot_value(
        self,
        *,
        slot_map: Mapping[str, Any],
        lexical_bindings: Mapping[str, Any],
        slot_name: str,
    ) -> Optional[str]:
        bound = lexical_bindings.get(slot_name)
        if isinstance(bound, ABCMapping):
            for key in ("lemma", "label", "surface", "text", "value"):
                value = _mapping_get_str(bound, key)
                if value:
                    return value
        else:
            value = _safe_str(bound)
            if value:
                return value

        raw = slot_map.get(slot_name)
        if isinstance(raw, ABCMapping):
            for key in ("lemma", "label", "surface", "text", "value"):
                value = _mapping_get_str(raw, key)
                if value:
                    return value
        return _safe_str(raw)

    # ------------------------------------------------------------------
    # Legacy frame helpers
    # ------------------------------------------------------------------

    def _frame_type(self, frame: Any) -> str:
        return str(getattr(frame, "frame_type", "") or "").strip().lower()

    def _extract_bio_fields(
        self,
        frame: Any,
    ) -> tuple[str, Optional[str], Optional[str]]:
        name: Optional[str] = None
        profession: Optional[str] = None
        nationality: Optional[str] = None

        if isinstance(frame, BioFrame):
            subject = getattr(frame, "subject", None)

            if isinstance(subject, ABCMapping):
                name = _mapping_get_str(subject, "name")
                profession = _mapping_get_str(subject, "profession")
                nationality = _mapping_get_str(subject, "nationality")
            else:
                name = _safe_str(getattr(subject, "name", None))
                profession = _safe_str(getattr(subject, "profession", None))
                nationality = _safe_str(getattr(subject, "nationality", None))

            return (name or "Unknown", profession, nationality)

        if isinstance(frame, Frame):
            subject = getattr(frame, "subject", {}) or {}
            properties = getattr(frame, "properties", {}) or {}

            if isinstance(subject, ABCMapping):
                name = _mapping_get_str(subject, "name")
                profession = _mapping_get_str(subject, "profession")
                nationality = _mapping_get_str(subject, "nationality")

            if isinstance(properties, ABCMapping):
                profession = profession or _mapping_get_str(properties, "profession")
                nationality = nationality or _mapping_get_str(properties, "nationality")
                name = name or _mapping_get_str(properties, "label")

            return (name or "Unknown", profession, nationality)

        if isinstance(frame, ABCMapping):
            subject = frame.get("subject")
            properties = frame.get("properties")

            if isinstance(subject, ABCMapping):
                name = _mapping_get_str(subject, "name")
                profession = _mapping_get_str(subject, "profession")
                nationality = _mapping_get_str(subject, "nationality")

            if isinstance(properties, ABCMapping):
                profession = profession or _mapping_get_str(properties, "profession")
                nationality = nationality or _mapping_get_str(properties, "nationality")
                name = name or _mapping_get_str(properties, "label")

            name = name or _mapping_get_str(frame, "name")
            profession = profession or _mapping_get_str(frame, "profession")
            nationality = nationality or _mapping_get_str(frame, "nationality")

            return (name or "Unknown", profession, nationality)

        raise DomainError(
            f"Unsupported frame object for bio extraction: {type(frame).__name__}"
        )