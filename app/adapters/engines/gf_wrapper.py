import sys
import structlog
from typing import List, Optional, Any
from pathlib import Path

try:
    import pgf
except ImportError:
    pgf = None

from app.core.ports.grammar_engine import IGrammarEngine
from app.core.domain.models import Sentence
from app.core.domain.frame import BioFrame
from app.core.domain.exceptions import (
    LanguageNotFoundError, 
    DomainError
)
from app.shared.config import settings
from app.shared.lexicon import lexicon_store

logger = structlog.get_logger()

class GFGrammarEngine(IGrammarEngine):
    """
    Primary Grammar Engine using the compiled PGF binary.
    Supports Dual-Path: Strict BioFrame and Prototype UniversalNode.
    """

    # Enterprise Mapping: ISO 639-1 (API) -> RGL Code (Grammar)
    # This bridges Zone A (2-letter) to Zone C (3-letter)
    ISO_2_TO_RGL = {
        "en": "Eng", "fr": "Fre", "de": "Ger", "it": "Ita", "es": "Spa",
        "nl": "Dut", "sv": "Swe", "ru": "Rus", "pl": "Pol", "fi": "Fin",
        "da": "Dan", "no": "Nor", "pt": "Por", "ro": "Ron", "zh": "Chi",
        "ja": "Jpn", "ar": "Ara", "hi": "Hin", "tr": "Tur", "he": "Heb"
    }

    def __init__(self, lib_path: str = None):
        # Fallback to AW_PGF_PATH if PGF_PATH isn't set
        self.pgf_path = getattr(settings, "PGF_PATH", None) or getattr(settings, "AW_PGF_PATH", "gf/AbstractWiki.pgf")
        self.grammar: Optional[pgf.PGF] = None
        
        print(f"[DEBUG] GFGrammarEngine initializing from: {self.pgf_path}")
        self._load_grammar()

    def _load_grammar(self):
        if not pgf:
            logger.warning("gf_runtime_missing", msg="pgf library not installed.")
            return

        path = Path(self.pgf_path)
        if path.exists():
            try:
                self.grammar = pgf.readPGF(str(path))
                logger.info("gf_grammar_loaded", path=str(path))
            except Exception as e:
                logger.error("gf_load_failed", error=str(e))
        else:
            logger.error("gf_file_not_found", path=str(path))

    async def generate(self, lang_code: str, frame: Any) -> Sentence:
        if not self.grammar:
            raise DomainError("GF Runtime is not loaded.")

        conc_name = self._resolve_concrete_name(lang_code)
        if not conc_name:
            avail = list(self.grammar.languages.keys())
            raise LanguageNotFoundError(f"Language {lang_code} not found. Available: {avail}")
        
        concrete = self.grammar.languages[conc_name]

        try:
            expr_str = self._convert_to_gf_ast(frame, lang_code)
        except Exception as e:
            logger.error("gf_ast_conversion_failed", error=str(e))
            raise DomainError(f"Failed to convert frame to GF AST: {str(e)}")

        try:
            expr = pgf.readExpr(expr_str)
            text = concrete.linearize(expr)
        except Exception as e:
            logger.error("gf_linearization_failed", lang=conc_name, command=expr_str, error=str(e))
            raise DomainError(f"Linearization failed for command {expr_str}: {str(e)}")

        return Sentence(
            text=text,
            lang_code=lang_code,
            debug_info={
                "engine": "gf_rgl",
                "concrete_grammar": conc_name,
                "command": expr_str
            }
        )

    def _resolve_concrete_name(self, lang_code: str) -> Optional[str]:
        """
        Resolves the concrete grammar name (e.g., WikiEng) from the ISO code (e.g., en).
        """
        # 1. Try Enterprise Mapping (en -> Eng -> WikiEng)
        rgl_suffix = self.ISO_2_TO_RGL.get(lang_code.lower())
        if rgl_suffix:
            candidate = f"Wiki{rgl_suffix}"
            if candidate in self.grammar.languages:
                return candidate

        # 2. Try Direct Capitalization (zul -> Zul -> WikiZul)
        target_suffix = lang_code.capitalize() 
        candidate = f"Wiki{target_suffix}"
        if candidate in self.grammar.languages:
            return candidate
            
        # 3. Fallback Scan
        for name in self.grammar.languages.keys():
            if name.endswith(target_suffix):
                return name
        return None

    def _convert_to_gf_ast(self, node: Any, lang_code: str) -> str:
        # --- PATH 1: Handle Strict BioFrame ---
        if isinstance(node, BioFrame):
            data = node.subject if isinstance(node.subject, dict) else {}
            
            name = data.get("name", "Unknown")
            prof = data.get("profession", "person")
            nat = data.get("nationality")

            s_expr = f'(mkEntityStr "{name}")'
            
            if prof and " " not in prof:
                p_expr = prof
            else:
                p_expr = f'(strProf "{prof}")'

            if nat:
                n_expr = f'(strNat "{nat}")'
                return f"mkBioFull {s_expr} {p_expr} {n_expr}"
            else:
                return f"mkBioProf {s_expr} {p_expr}"

        # --- PATH 2: Handle Primitives ---
        if isinstance(node, (str, int, float)):
            s_node = str(node)
            
            # Lookup in Lexicon (Zone B) using the ISO-2 code (lang_code)
            # The Lexicon Store expects 2-letter codes for file paths
            entry = lexicon_store.lookup(s_node, lang_code)
            lemma = entry.lemma if entry else s_node
            
            if lemma.replace('.', '', 1).isdigit():
                return lemma
            if lemma.startswith('"'):
                return lemma
            return f'"{lemma}"'

        # --- PATH 3: Handle Raw Dictionaries ---
        func_name = getattr(node, "function", None) or (node.get("function") if isinstance(node, dict) else None)
        
        if not func_name:
             raise ValueError(f"Invalid Node: Missing function attribute. Got {type(node)}")

        args = getattr(node, "args", [])
        if isinstance(node, dict):
            args = node.get("args", [])

        processed_args = [self._convert_to_gf_ast(arg, lang_code) for arg in args]
        
        if not processed_args:
             return func_name
             
        args_str = " ".join([f"({arg})" for arg in processed_args])
        return f"{func_name} {args_str}"

    async def get_supported_languages(self) -> List[str]:
        if not self.grammar: return []
        return [name[-3:].lower() for name in self.grammar.languages.keys()]

    async def reload(self) -> None:
        self._load_grammar()

    async def health_check(self) -> bool:
        return self.grammar is not None