# app/adapters/engines/gf_engine.py
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import pgf  # GF Python Bindings
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.domain.exceptions import DomainError, ExternalServiceError, LanguageNotReadyError
from app.core.domain.frame import BioFrame
from app.core.domain.models import Frame, Sentence
from app.core.ports.grammar_engine import IGrammarEngine
from app.shared.config import settings

logger = structlog.get_logger()

GF_TIMEOUT_SECONDS = 30

# Exceptions we will retry on (e.g., transient GF/runtime errors)
RETRYABLE_EXCEPTIONS = (ExternalServiceError, subprocess.TimeoutExpired)

_BIO_FRAME_TYPES = {
    "bio",
    "biography",
    "entity.person",
    "entity_person",
    "person",
    "entity.person.v1",
    "entity.person.v2",
}


def _normalize_pgf_path(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return value
    if value.endswith(("/", "\\")) or not value.lower().endswith(".pgf"):
        return os.path.join(value, "semantik_architect.pgf")
    return value


def _effective_pgf_path() -> str:
    """
    Prefer explicit env overrides (containers/tests), then validated settings.
    Supports both PGF_PATH (preferred) and legacy AW_PGF_PATH.
    """
    env_path = os.getenv("PGF_PATH") or os.getenv("AW_PGF_PATH")
    if env_path:
        return _normalize_pgf_path(env_path)
    return _normalize_pgf_path(getattr(settings, "PGF_PATH", "") or "")


def _repo_root() -> Path:
    for attr in ("REPO_ROOT", "ROOT_DIR", "PROJECT_ROOT", "FILESYSTEM_REPO_PATH"):
        if hasattr(settings, attr):
            val = getattr(settings, attr)
            if val:
                return Path(val).resolve()
    # .../app/adapters/engines/gf_engine.py -> repo root is typically 4 levels up
    return Path(__file__).resolve().parents[3]


def _load_iso_to_wiki_map() -> Dict[str, Any]:
    """
    Load ISO->Wiki mapping from data/config/iso_to_wiki.json (canonical),
    falling back to gf/data/config/iso_to_wiki.json (legacy).
    """
    root = _repo_root()
    candidates = [
        root / "data" / "config" / "iso_to_wiki.json",
        root / "gf" / "data" / "config" / "iso_to_wiki.json",
    ]
    for p in candidates:
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    logger.info("iso_map_loaded", path=str(p), entries=len(data))
                    return data
        except Exception as e:
            logger.warning("iso_map_load_failed", path=str(p), error=str(e))
    logger.warning("iso_map_missing", tried=[str(p) for p in candidates])
    return {}


def _extract_wiki_suffix(raw_val: Any) -> Optional[str]:
    """
    iso_to_wiki.json values may be:
      - "WikiEng" or "Eng"
      - {"wiki": "WikiEng", ...}
    Returns suffix like "Eng".
    """
    if raw_val is None:
        return None
    if isinstance(raw_val, dict):
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
    return s if s else None


def _escape_gf_string(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace('"', '\\"')


def _mapping_get_str(data: Any, key: str) -> Optional[str]:
    if isinstance(data, Mapping):
        return _safe_str(data.get(key))
    return None


class GFEngine(IGrammarEngine):
    """
    Adapter implementation for IGrammarEngine using the Grammatical Framework (GF)
    Python 'pgf' bindings.

    This version aligns with the current semantic/domain layer:
      - BioFrame uses nested subject data
      - legacy Frame uses subject/properties dicts
      - abstract GF exposes mkBioProf / mkBioFull / mkBioNat
    """

    def __init__(self):
        self._iso_map: Dict[str, Any] = _load_iso_to_wiki_map()

        # Reverse lookup: "Eng" -> "en"
        self._wiki_to_iso2: Dict[str, str] = {}
        for k, v in self._iso_map.items():
            suf = _extract_wiki_suffix(v)
            if suf:
                self._wiki_to_iso2[suf] = str(k).lower()
                self._wiki_to_iso2[suf.lower()] = str(k).lower()

        self._pgf = self._load_pgf()
        self._supported_gf_langs = self._get_supported_gf_langs()
        self._supported_languages = self._get_supported_languages()

    def _load_pgf(self) -> Optional[pgf.PGF]:
        """Loads the master PGF file (semantik_architect.pgf) into memory."""
        pgf_file = _effective_pgf_path()
        if not pgf_file or not os.path.exists(pgf_file):
            logger.error("pgf_file_missing", path=pgf_file or "(empty)")
            return None

        try:
            pgf_grammar = pgf.readPGF(pgf_file)
            logger.info("pgf_loaded", path=pgf_file, languages=len(pgf_grammar.languages))
            return pgf_grammar
        except Exception as e:
            logger.error("pgf_load_failed", path=pgf_file, error=str(e))
            return None

    def _get_supported_gf_langs(self) -> set[str]:
        """Raw GF concrete module names: {'WikiEng', 'WikiFre', ...}."""
        if self._pgf:
            return set(self._pgf.languages.keys())
        return set()

    def _get_supported_languages(self) -> set[str]:
        """
        Preferred output: ISO-2 codes (e.g. {'en','fr',...}) when iso_to_wiki.json
        provides a reverse map. Fallback: wiki suffix lowercased.
        """
        out: set[str] = set()
        for name in self._supported_gf_langs:
            suf = str(name).replace("Wiki", "").strip()
            if not suf:
                continue
            iso2 = self._wiki_to_iso2.get(suf) or self._wiki_to_iso2.get(suf.lower())
            out.add(iso2 if iso2 else suf.lower())
        return out

    def _gf_lang_name(self, lang_code: str) -> str:
        """
        Convert incoming language code into a GF concrete module name.
        Accepts:
          - ISO2 ('fr')
          - existing wiki suffix ('Fre')
          - existing GF module name ('WikiFre')
        """
        code = (lang_code or "").strip()
        if not code:
            return "WikiUnknown"

        if code.startswith("Wiki") and len(code) > 4:
            return code

        raw_val = self._iso_map.get(code) or self._iso_map.get(code.lower())
        suf = _extract_wiki_suffix(raw_val)

        if not suf:
            stripped = code.replace("Wiki", "").strip()
            if len(stripped) == 2:
                suf = stripped.upper()
            else:
                suf = stripped[:1].upper() + stripped[1:]

        return f"Wiki{suf}"

    def _resolve_loaded_gf_lang_name(self, lang_code: str) -> Optional[str]:
        """
        Resolve a language code against currently loaded grammar languages.
        """
        if not self._pgf:
            return None

        # Exact / already concrete
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

        # Suffix fallback: "fre" -> WikiFre, "eng" -> WikiEng, etc.
        suffix = raw.replace("Wiki", "").strip().lower()
        for concrete in self._pgf.languages.keys():
            if concrete.lower() == f"wiki{suffix}" or concrete.lower().endswith(suffix):
                return concrete

        return None

    def is_language_ready(self, lang_code: str) -> bool:
        """Checks if the required concrete syntax is loaded in the PGF."""
        if not self._pgf:
            return False
        return self._resolve_loaded_gf_lang_name(lang_code) is not None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True,
    )
    async def generate(self, lang_code: str, frame: Frame) -> Sentence:
        """Converts the semantic Frame into text using the GF engine."""
        if not self._pgf:
            raise ExternalServiceError("GF Engine is not initialized. PGF file missing or corrupt.")

        gf_lang_name = self._resolve_loaded_gf_lang_name(lang_code)
        if not gf_lang_name:
            expected = self._gf_lang_name(lang_code)
            raise LanguageNotReadyError(
                f"Language '{lang_code}' not found (expected concrete '{expected}')."
            )

        try:
            ast_string = self._map_frame_to_ast(frame)
            if not ast_string:
                raise DomainError(f"Frame mapping failed for type: {getattr(frame, 'frame_type', 'unknown')}")
            ast_expr = pgf.readExpr(ast_string)
        except DomainError:
            raise
        except Exception as e:
            logger.error(
                "ast_mapping_failed",
                frame_type=getattr(frame, "frame_type", "unknown"),
                error=str(e),
            )
            raise DomainError(f"Failed to convert frame to AST: {str(e)}")

        concrete_syntax = self._pgf.languages[gf_lang_name]
        try:
            text = concrete_syntax.linearize(ast_expr)
            return Sentence(
                text=text,
                lang_code=lang_code,
                debug_info={"ast": ast_string, "gf_lang": gf_lang_name},
            )
        except pgf.ParseError as e:
            logger.error("gf_linearization_failed", lang=lang_code, ast=ast_string, error=str(e))
            raise DomainError(f"GF Linearization failed (ParseError): {str(e)}")
        except Exception as e:
            logger.error("gf_runtime_error", lang=lang_code, ast=ast_string, error=str(e))
            raise ExternalServiceError(f"GF Runtime Error during linearization: {str(e)}")

    def _frame_type(self, frame: Any) -> str:
        return str(getattr(frame, "frame_type", "") or "").strip().lower()

    def _extract_bio_fields(self, frame: Any) -> tuple[str, Optional[str], Optional[str]]:
        """
        Supports:
          - BioFrame(subject={name, profession, nationality, ...})
          - legacy Frame(subject={}, properties={})
          - dict-like payloads if they ever reach this layer
        """
        name: Optional[str] = None
        profession: Optional[str] = None
        nationality: Optional[str] = None

        if isinstance(frame, BioFrame):
            subject = getattr(frame, "subject", None)

            if isinstance(subject, Mapping):
                name = _mapping_get_str(subject, "name")
                profession = _mapping_get_str(subject, "profession")
                nationality = _mapping_get_str(subject, "nationality")
            else:
                name = _safe_str(getattr(subject, "name", None))
                profession = _safe_str(getattr(subject, "profession", None))
                nationality = _safe_str(getattr(subject, "nationality", None))

            return (
                name or "Unknown",
                profession,
                nationality,
            )

        if isinstance(frame, Frame):
            subject = getattr(frame, "subject", {}) or {}
            properties = getattr(frame, "properties", {}) or {}

            if isinstance(subject, Mapping):
                name = _mapping_get_str(subject, "name")
                profession = _mapping_get_str(subject, "profession")
                nationality = _mapping_get_str(subject, "nationality")

            if isinstance(properties, Mapping):
                profession = profession or _mapping_get_str(properties, "profession")
                nationality = nationality or _mapping_get_str(properties, "nationality")
                name = name or _mapping_get_str(properties, "label")

            return (
                name or "Unknown",
                profession,
                nationality,
            )

        if isinstance(frame, Mapping):
            subject = frame.get("subject")
            properties = frame.get("properties")

            if isinstance(subject, Mapping):
                name = _mapping_get_str(subject, "name")
                profession = _mapping_get_str(subject, "profession")
                nationality = _mapping_get_str(subject, "nationality")

            if isinstance(properties, Mapping):
                profession = profession or _mapping_get_str(properties, "profession")
                nationality = nationality or _mapping_get_str(properties, "nationality")
                name = name or _mapping_get_str(properties, "label")

            name = name or _mapping_get_str(frame, "name")
            profession = profession or _mapping_get_str(frame, "profession")
            nationality = nationality or _mapping_get_str(frame, "nationality")

            return (
                name or "Unknown",
                profession,
                nationality,
            )

        raise DomainError(f"Unsupported frame object for bio extraction: {type(frame).__name__}")

    def _map_frame_to_ast(self, frame: Any) -> Optional[str]:
        """
        Map a semantic frame to the current abstract GF API.

        Grammar contract:
          mkEntityStr : String -> Entity
          strProf     : String -> Profession
          strNat      : String -> Nationality
          mkBioProf   : Entity -> Profession -> Statement
          mkBioNat    : Entity -> Nationality -> Statement
          mkBioFull   : Entity -> Profession -> Nationality -> Statement
        """
        frame_type = self._frame_type(frame)

        if frame_type not in _BIO_FRAME_TYPES:
            return None

        name, profession, nationality = self._extract_bio_fields(frame)

        entity_expr = f'mkEntityStr "{_escape_gf_string(name)}"'
        prof_val = _safe_str(profession)
        nat_val = _safe_str(nationality)

        # Best-effort semantics:
        # - profession + nationality -> mkBioFull
        # - profession only          -> mkBioProf
        # - nationality only         -> mkBioNat
        # - nothing                  -> fallback profession "person"
        if prof_val and nat_val:
            prof_expr = f'strProf "{_escape_gf_string(prof_val)}"'
            nat_expr = f'strNat "{_escape_gf_string(nat_val)}"'
            return f"mkBioFull ({entity_expr}) ({prof_expr}) ({nat_expr})"

        if prof_val:
            prof_expr = f'strProf "{_escape_gf_string(prof_val)}"'
            return f"mkBioProf ({entity_expr}) ({prof_expr})"

        if nat_val:
            nat_expr = f'strNat "{_escape_gf_string(nat_val)}"'
            return f"mkBioNat ({entity_expr}) ({nat_expr})"

        return f'mkBioProf ({entity_expr}) (strProf "person")'

    async def health_check(self) -> bool:
        """Verifies the engine is initialized and the PGF file is accessible."""
        is_ready = self._pgf is not None and bool(self._supported_gf_langs)
        if not is_ready:
            logger.warning("gf_health_check_failed", reason="PGF not loaded or no languages found")
        return is_ready