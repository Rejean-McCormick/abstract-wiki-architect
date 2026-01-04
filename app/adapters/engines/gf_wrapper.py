# app/adapters/engines/gf_wrapper.py
import json
import structlog
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    Supports:
      - BioFrame / Frame (internal domain)
      - Ninai/UniversalNode dict trees (external protocol)
    """

    def __init__(self, lib_path: str | None = None):
        # NOTE: lib_path is kept for compatibility with DI wiring; PGF path is controlled by settings.
        self.pgf_path = getattr(settings, "PGF_PATH", None) or getattr(
            settings, "AW_PGF_PATH", "gf/AbstractWiki.pgf"
        )

        self.grammar: Optional[Any] = None
        self.inventory: Dict[str, Any] = {}
        self.iso_map: Dict[str, str] = {}

        self._load_inventory()
        self._load_iso_config()
        self._load_grammar()

    # ----------------------------
    # Loading helpers
    # ----------------------------
    def _load_inventory(self) -> None:
        try:
            candidates: list[Path] = []
            if (
                settings
                and hasattr(settings, "FILESYSTEM_REPO_PATH")
                and settings.FILESYSTEM_REPO_PATH
            ):
                repo_root = Path(settings.FILESYSTEM_REPO_PATH)
                candidates.append(repo_root / "data" / "indices" / "rgl_inventory.json")

            candidates.append(
                Path(__file__).resolve().parents[3]
                / "data"
                / "indices"
                / "rgl_inventory.json"
            )

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
        try:
            candidates: list[Path] = []
            if (
                settings
                and hasattr(settings, "FILESYSTEM_REPO_PATH")
                and settings.FILESYSTEM_REPO_PATH
            ):
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
                self.iso_map = {}
                return

            with config_path.open("r", encoding="utf-8") as f:
                raw_data = json.load(f)

            iso_map: Dict[str, str] = {}
            for code, value in (raw_data or {}).items():
                if not isinstance(code, str):
                    continue
                if isinstance(value, dict):
                    suffix = value.get("wiki")
                    if isinstance(suffix, str) and suffix:
                        iso_map[code.lower().strip()] = suffix
                elif isinstance(value, str):
                    iso_map[code.lower().strip()] = value.replace("Wiki", "")
            self.iso_map = iso_map
        except Exception:
            self.iso_map = {}

    def _load_grammar(self) -> None:
        if not pgf:
            return
        path = Path(self.pgf_path)
        if not path.exists():
            return
        try:
            self.grammar = pgf.readPGF(str(path))
        except Exception as e:
            self.grammar = None
            logger.error("gf_load_failed", error=str(e), pgf_path=str(path))

    # ----------------------------
    # Public API (IGrammarEngine)
    # ----------------------------
    async def generate(self, lang_code: str, frame: Any) -> Sentence:
        """
        Generate text from:
          - BioFrame
          - Frame (domain)
          - dict (either BioFrame-like payload or Ninai/UniversalNode)
        """
        if not self.grammar:
            return Sentence(text="<GF Runtime Not Loaded>", lang_code=lang_code)

        # 1) Ninai/UniversalNode dict: if it looks like a constructor tree, linearize it directly
        if isinstance(frame, dict) and ("function" in frame or "args" in frame):
            ast_str = self._convert_to_gf_ast(frame, lang_code)
            text = self.linearize(ast_str, lang_code)
            if not text:
                text = "<LinearizeError>"
            return Sentence(text=text, lang_code=lang_code, debug_info={"ast": ast_str})

        # 2) Bio-ish domain object or dict payload
        bio = self._coerce_to_bio_frame(frame)
        ast_str = self._convert_to_gf_ast(bio, lang_code)
        text = self.linearize(ast_str, lang_code)

        # Fallback: never return empty
        if not text or text.strip() in {"[]", ""}:
            name = (bio.name or "").strip() or "<Unknown>"
            text = name

        return Sentence(text=text, lang_code=lang_code, debug_info={"ast": ast_str})

    def parse(self, sentence: str, language: str):
        if not self.grammar:
            return []
        if language not in self.grammar.languages:
            concrete = self._resolve_concrete_name(language)
            if not concrete:
                return []
            language = concrete
        concrete_grammar = self.grammar.languages[language]
        try:
            return concrete_grammar.parse(sentence)
        except Exception:
            return []

    def linearize(self, expr: Any, language: str) -> str:
        if not self.grammar:
            return "<GF Runtime Not Loaded>"

        if language not in self.grammar.languages:
            concrete = self._resolve_concrete_name(language)
            if not concrete:
                return f"<Language '{language}' not found>"
            language = concrete

        concrete_grammar = self.grammar.languages[language]

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
        if not self.grammar:
            return []
        return list(self.grammar.languages.keys())

    async def reload(self) -> None:
        self._load_grammar()
        self._load_inventory()
        self._load_iso_config()

    async def health_check(self) -> bool:
        return self.grammar is not None

    # ----------------------------
    # Language resolution
    # ----------------------------
    def _resolve_concrete_name(self, lang_code: str) -> Optional[str]:
        if not self.grammar:
            return None
        iso_clean = (lang_code or "").lower().strip()

        rgl_suffix = self.iso_map.get(iso_clean)
        if rgl_suffix:
            candidate = f"Wiki{rgl_suffix}"
            if candidate in self.grammar.languages:
                return candidate

        if len(iso_clean) == 3:
            candidate = f"Wiki{iso_clean.capitalize()}"
            if candidate in self.grammar.languages:
                return candidate

        return None

    # ----------------------------
    # Conversion helpers
    # ----------------------------
    @staticmethod
    def _escape_gf_str(s: str) -> str:
        return (s or "").replace("\\", "\\\\").replace('"', '\\"')

    def _coerce_to_bio_frame(self, obj: Any) -> BioFrame:
        if isinstance(obj, BioFrame):
            return obj

        # Domain Frame -> BioFrame (best-effort)
        if isinstance(obj, Frame):
            return BioFrame(
                frame_type="bio",
                subject=obj.subject,
                properties=getattr(obj, "properties", {}) or {},
                context_id=getattr(obj, "context_id", "") or "",
                meta=getattr(obj, "meta", {}) or {},
            )

        # Dict payload -> BioFrame (accept both flat and {subject,properties} shapes)
        if isinstance(obj, dict):
            if obj.get("frame_type") == "bio" and ("subject" in obj or "name" in obj):
                subject = obj.get("subject") or {}
                props = obj.get("properties") or {}
                # Support “flat” convenience keys
                if obj.get("name") and isinstance(subject, dict):
                    subject = {**subject, "name": obj.get("name")}
                if obj.get("profession") and isinstance(subject, dict):
                    subject = {**subject, "profession": obj.get("profession")}
                if obj.get("nationality") and isinstance(subject, dict):
                    subject = {**subject, "nationality": obj.get("nationality")}
                if obj.get("gender") and isinstance(subject, dict):
                    subject = {**subject, "gender": obj.get("gender")}

                return BioFrame(
                    frame_type="bio",
                    subject=subject,
                    properties=props,
                    context_id=obj.get("context_id") or "",
                    meta=obj.get("meta") or {},
                )

        raise ValueError("Unsupported frame payload for Bio generation")

    def _bio_fields(self, frame: BioFrame) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
        name = (getattr(frame, "name", None) or "").strip()
        gender = getattr(frame, "gender", None)

        profession = None
        nationality = None

        subj = getattr(frame, "subject", None)
        if isinstance(subj, dict):
            profession = subj.get("profession")
            nationality = subj.get("nationality")
            if not name:
                name = (subj.get("name") or "").strip()
            if gender is None:
                gender = subj.get("gender")
        else:
            # subject may be a Pydantic model (Entity). Use getattr safely.
            profession = getattr(subj, "profession", None)
            nationality = getattr(subj, "nationality", None)
            if not name:
                name = (getattr(subj, "name", None) or "").strip()
            if gender is None:
                gender = getattr(subj, "gender", None)

        return name, profession, nationality, gender

    def _convert_to_gf_ast(self, node: Any, lang_code: str) -> str:
        # --- BioFrame -> GF AST (preferred AbstractWiki surface constructors) ---
        if isinstance(node, BioFrame):
            name, prof, nat, _gender = self._bio_fields(node)
            name_esc = self._escape_gf_str(name or "Unknown")
            prof_esc = self._escape_gf_str(prof or "person")
            nat_esc = self._escape_gf_str(nat or "")

            entity = f'mkEntityStr "{name_esc}"'
            prof_expr = f'strProf "{prof_esc}"'

            if nat_esc:
                nat_expr = f'strNat "{nat_esc}"'
                return f"mkBioFull ({entity}) ({prof_expr}) ({nat_expr})"

            return f"mkBioProf ({entity}) ({prof_expr})"

        # --- Ninai/UniversalNode dict -> GF AST ---
        if isinstance(node, dict):
            func = node.get("function")
            if not func:
                # Required by tests
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

            # If the grammar can't interpret RGL-like constructors (e.g. mkCl),
            # degrade to a literal string so we still get meaningful output.
            if func == "mkCl":
                if self._linearizes_as_placeholder(candidate, lang_code):
                    literal = self._flatten_ninai_to_literal(node)
                    return literal
            return candidate

        # --- primitives ---
        if isinstance(node, str):
            return f'"{self._escape_gf_str(node)}"'
        if node is None:
            return '""'
        return f'"{self._escape_gf_str(str(node))}"'

    def _linearizes_as_placeholder(self, expr_str: str, lang_code: str) -> bool:
        """
        Best-effort probe: if linearization yields bracketed placeholders (e.g. "[mkCl]"),
        treat it as unsupported by the current PGF.
        """
        if not (self.grammar and pgf):
            return False

        conc_name = None
        if lang_code in self.grammar.languages:
            conc_name = lang_code
        else:
            conc_name = self._resolve_concrete_name(lang_code)

        if not conc_name or conc_name not in self.grammar.languages:
            return False

        try:
            expr_obj = pgf.readExpr(expr_str)
            out = self.grammar.languages[conc_name].linearize(expr_obj)
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
