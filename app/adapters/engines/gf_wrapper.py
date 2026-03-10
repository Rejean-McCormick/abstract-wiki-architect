# app/adapters/engines/gf_wrapper.py
import asyncio
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

try:
    import pgf
except ImportError:
    pgf = None

from app.core.domain.frame import BioFrame
from app.core.domain.models import Frame, Sentence
from app.shared.config import settings

logger = structlog.get_logger()


class GFGrammarEngine:
    """
    Primary Grammar Engine using the compiled PGF binary.

    Key runtime behavior:
    - Async (API server): lazy-load via await _ensure_grammar() (non-blocking startup).
    - Sync (CLI/tools): first access to .grammar triggers a safe synchronous load.
      This fixes tools like universal_test_runner which check engine.grammar is not None.

    Payload tolerance:
    - Canonical BioFrame instances
    - Legacy flat bio payloads
    - Flat entity.person payloads from the Dev GUI
    - Dicts that place fields in subject / main_entity / properties / top-level
    """

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

        # Language normalization maps (from iso_to_wiki.json + inventory fallback)
        # - wiki_to_iso2: maps aliases (wiki/iso3/wikixxx/etc) -> iso2
        # - iso2_to_wiki: maps iso2 -> wiki suffix (Fre/Ger/Eng/etc)
        # - iso2_to_iso3: maps iso2 -> iso3 (fra/deu/etc) when known
        self.wiki_to_iso2: Dict[str, str] = {}
        self.iso2_to_wiki: Dict[str, str] = {}
        self.iso2_to_iso3: Dict[str, str] = {}

        # Diagnostics
        self.last_load_error: Optional[str] = None
        self.last_load_error_type: Optional[str] = None  # "pgf_missing" | "pgf_file_missing" | "pgf_read_failed"

        self._async_load_lock: asyncio.Lock = asyncio.Lock()
        self._thread_load_lock: threading.Lock = threading.Lock()

        self._load_inventory()
        self._load_iso_config()
        self._derive_wiki_from_inventory()

    # ----------------------------
    # Path helpers
    # ----------------------------
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

    # ----------------------------
    # Grammar access (sync tools fix)
    # ----------------------------
    @property
    def grammar(self) -> Optional[Any]:
        if self._grammar is not None:
            return self._grammar

        # If we're inside a running event loop, do NOT block.
        try:
            asyncio.get_running_loop()
            return None
        except RuntimeError:
            self._load_grammar_sync()
            return self._grammar

    @grammar.setter
    def grammar(self, value: Optional[Any]) -> None:
        self._grammar = value

    # ----------------------------
    # Loading helpers
    # ----------------------------
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
        """
        Loads config/iso_to_wiki.json (or data/config/iso_to_wiki.json) and builds:
          - wiki_to_iso2
          - iso2_to_wiki
          - iso2_to_iso3
        This matches how tools/language_health/norm.py expects to normalize codes.
        """
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

            # Accept both:
            #  - iso2 -> {wiki: "Fre", iso3: "fra", ...}
            #  - alias (fre/fra/wikiFre) -> iso2
            for k, v in raw.items():
                if not isinstance(k, str):
                    continue
                kk = k.strip().casefold()
                if not kk:
                    continue

                if isinstance(v, dict):
                    iso2 = v.get("iso2")
                    if not (isinstance(iso2, str) and len(iso2.strip()) == 2):
                        if len(kk) == 2 and kk.isalpha():
                            iso2 = kk
                        else:
                            iso2 = None
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

                    # Case A: alias -> iso2
                    if len(vv) == 2 and vv.isalpha():
                        self.wiki_to_iso2[kk] = vv
                        if kk.startswith("wiki") and len(kk) > 4:
                            self.wiki_to_iso2[kk[4:]] = vv
                        self.wiki_to_iso2[vv] = vv
                        self.wiki_to_iso2[f"wiki{vv}"] = vv
                        continue

                    # Case B: iso2 -> wiki suffix
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
        """
        Inventory fallback: if iso2_to_wiki is missing entries, try to infer the
        3-letter wiki suffix from module names like SyntaxFre / LexiconGer.
        """
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
                mm = m.strip()
                hit = rx.match(mm)
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
            except Exception as e:
                self._grammar = None
                self.last_load_error_type = "pgf_read_failed"
                self.last_load_error = f"pgf.readPGF failed: {e}"
                logger.error("gf_load_failed", error=str(e), pgf_path=str(path))

    async def _ensure_grammar(self) -> None:
        if self._grammar is not None:
            return
        async with self._async_load_lock:
            if self._grammar is None:
                await asyncio.to_thread(self._load_grammar_sync)

    # ----------------------------
    # Public API
    # ----------------------------
    async def status(self) -> Dict[str, Any]:
        await self._ensure_grammar()
        payload: Dict[str, Any] = {
            "loaded": self._grammar is not None,
            "pgf_path": str(self.pgf_path),
            "error_type": self.last_load_error_type,
            "error": self.last_load_error,
        }
        if self._grammar is not None:
            payload["language_count"] = len(getattr(self._grammar, "languages", {}) or {})
        return payload

    async def generate(self, lang_code: str, frame: Any) -> Sentence:
        await self._ensure_grammar()

        if not self._grammar:
            dbg = {
                "pgf_path": str(self.pgf_path),
                "error_type": self.last_load_error_type,
                "error": self.last_load_error,
            }
            return Sentence(text="<GF Runtime Not Loaded>", lang_code=lang_code, debug_info=dbg)

        # 1) Ninai / UniversalNode-like dict
        if isinstance(frame, dict) and ("function" in frame or "args" in frame):
            ast_str = self._convert_to_gf_ast(frame, lang_code)
            text = self.linearize(ast_str, lang_code)
            if not text:
                text = "<LinearizeError>"
            return Sentence(
                text=text,
                lang_code=lang_code,
                debug_info={
                    "ast": ast_str,
                    "resolved_language": self._resolve_concrete_name(lang_code),
                },
            )

        # 2) Bio-ish domain object or dict payload
        bio = self._coerce_to_bio_frame(frame)
        ast_str = self._convert_to_gf_ast(bio, lang_code)
        text = self.linearize(ast_str, lang_code)

        # Only soft-fallback on empty / placeholder-ish outputs, not on explicit runtime errors.
        if not text or text.strip() in {"[]", ""}:
            name = (bio.name or "").strip() or "<Unknown>"
            text = name

        return Sentence(
            text=text,
            lang_code=lang_code,
            debug_info={
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
            except Exception as e:
                return f"<LinearizeError: {e}>"
        else:
            expr_obj = expr

        try:
            return concrete_grammar.linearize(expr_obj)
        except Exception as e:
            return f"<LinearizeError: {e}>"

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

    # ----------------------------
    # Language resolution
    # ----------------------------
    def _norm_to_iso2(self, code: str) -> Optional[str]:
        """
        Normalize (iso2/iso3/wiki/wikixxx) -> iso2 using wiki_to_iso2.
        Mirrors tools/language_health/norm.py behavior.
        """
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
        """
        Resolve external language inputs into a concrete PGF language key present in grammar.languages.
        Supports:
          - exact concrete keys (WikiEng, WikiGer, ...)
          - iso2 (en/de/fr)
          - wiki suffixes (eng/ger/fre/...)
          - iso3 (fra/deu/...) when configured
          - wikixxx (wikiger, wikifre, ...)
        """
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

        for p in probes:
            for k in g.languages.keys():
                kl = k.casefold()
                if kl == p or kl == f"wiki{p}":
                    return k
                if kl.endswith(p) or kl.endswith(f"wiki{p}"):
                    return k

        return None

    # ----------------------------
    # Small payload helpers
    # ----------------------------
    @staticmethod
    def _escape_gf_str(s: str) -> str:
        return (s or "").replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _clean_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            s = value.strip()
            return s or None
        s = str(value).strip()
        return s or None

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _first_non_empty(self, *sources: Any) -> Optional[str]:
        for src in sources:
            if isinstance(src, dict):
                for v in src.values():
                    s = self._clean_str(v)
                    if s:
                        return s
            else:
                s = self._clean_str(src)
                if s:
                    return s
        return None

    def _pick(self, source: Dict[str, Any], keys: tuple[str, ...]) -> Optional[str]:
        for key in keys:
            val = self._clean_str(source.get(key))
            if val:
                return val
        return None

    def _normalize_gender(self, value: Any) -> Optional[str]:
        s = self._clean_str(value)
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
        """
        Merge bio-relevant fields from:
          - payload.subject
          - payload.main_entity
          - payload.properties
          - payload top-level flat keys

        Precedence: top-level > properties > main_entity > subject
        """
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

    # ----------------------------
    # Conversion helpers
    # ----------------------------
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
        name = self._clean_str(getattr(frame, "name", None)) or ""
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
            profession = self._clean_str(getattr(subj, "profession", None))
            nationality = self._clean_str(getattr(subj, "nationality", None))

            if not name:
                name = self._clean_str(getattr(subj, "name", None)) or ""
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

            # Most specific first:
            # - profession + nationality -> mkBioFull
            # - nationality only         -> mkBioNat
            # - profession only          -> mkBioProf
            # - nothing                  -> mkBioProf(..., "person")
            if prof_esc and nat_esc:
                prof_expr = f'strProf "{prof_esc}"'
                nat_expr = f'strNat "{nat_esc}"'
                return f"mkBioFull ({entity}) ({prof_expr}) ({nat_expr})"

            if nat_esc:
                nat_expr = f'strNat "{nat_esc}"'
                return f"mkBioNat ({entity}) ({nat_expr})"

            prof_expr = f'strProf "{self._escape_gf_str(prof or 'person')}"'
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