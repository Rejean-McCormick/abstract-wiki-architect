# app/adapters/engines/gf_wrapper.py
import sys
import structlog
from typing import List, Optional, Any
from pathlib import Path

try:
    import pgf
except ImportError:
    pgf = None

from app.core.ports.grammar_engine import IGrammarEngine
from app.core.domain.models import Frame, Sentence
from app.core.domain.exceptions import (
    LanguageNotFoundError, 
    DomainError
)
from app.shared.config import settings

logger = structlog.get_logger()

class GFGrammarEngine(IGrammarEngine):
    """
    Primary Grammar Engine using the compiled PGF binary.
    """

    def __init__(self, lib_path: str = None):
        self.pgf_path = settings.AW_PGF_PATH
        self.grammar: Optional[pgf.PGF] = None
        
        # DEBUG: Confirm initialization of the new logic
        print(f"[DEBUG] GFGrammarEngine (Flexible Mode) initializing from: {self.pgf_path}")
        self._load_grammar()

    def _load_grammar(self):
        """Loads the .pgf file into memory."""
        if not pgf:
            logger.warning("gf_runtime_missing", msg="pgf library not installed. Engine disabled.")
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

    async def generate(self, lang_code: str, frame: Frame) -> Sentence:
        """
        1. Look up Concrete Grammar (e.g., 'WikiFra' for 'fra').
        2. Convert Frame -> PGF Expression.
        3. Linearize Expression -> Text.
        """
        if not self.grammar:
            raise DomainError("GF Runtime is not loaded or PGF file is missing.")

        # 1. Resolve Concrete Language
        conc_name = self._resolve_concrete_name(lang_code)
        if not conc_name:
            # Helpful error message listing available languages
            avail = list(self.grammar.languages.keys())
            raise LanguageNotFoundError(f"Language '{lang_code}' not found. Available: {avail}")
        
        concrete = self.grammar.languages[conc_name]

        # 2. Construct AST (Abstract Syntax Tree)
        try:
            expr = self._build_expr(frame)
        except Exception as e:
            logger.error("gf_ast_construction_failed", frame=frame.frame_type, error=str(e))
            raise DomainError(f"Failed to construct grammar tree: {str(e)}")

        # 3. Linearize
        try:
            text = concrete.linearize(expr)
        except Exception as e:
            logger.error("gf_linearization_failed", lang=conc_name, error=str(e))
            raise DomainError(f"Linearization failed: {str(e)}")

        return Sentence(
            text=text,
            lang_code=lang_code,
            debug_info={
                "engine": "gf_rgl",
                "concrete_grammar": conc_name,
                "ast": str(expr)
            }
        )

    def _resolve_concrete_name(self, lang_code: str) -> Optional[str]:
        """
        Maps ISO code (fra) to PGF concrete name (WikiFra).
        """
        target_suffix = lang_code.capitalize() 
        
        # 1. Direct Lookup (e.g. WikiEng)
        candidate = f"Wiki{target_suffix}"
        if candidate in self.grammar.languages:
            return candidate

        # 2. Suffix Search (fallback)
        for name in self.grammar.languages.keys():
            if name.endswith(target_suffix):
                return name
        return None

    def _build_expr(self, frame: Frame) -> Any:
        """
        Converts the generic Frame into a PGF Expression.
        Handles both Constants (John) and Functions (mkBio).
        """
        fname = frame.frame_type
        
        # 1. Try exact name match (e.g. "John")
        if fname not in self.grammar.functions:
            # 2. Try RGL convention (e.g. "mkJohn")
            fname_rgl = f"mk{frame.frame_type.capitalize()}" 
            if fname_rgl in self.grammar.functions:
                fname = fname_rgl
            else:
                # Failure
                raise DomainError(f"Function '{fname}' (or '{fname_rgl}') not found in grammar.")

        # 3. Handle Constants (0 arguments)
        # If no subject is provided, we assume it's a constant like "John" or "Apple"
        if not frame.subject:
             return pgf.Expr(fname, [])

        # 4. Handle Functions with Arguments (Simplified)
        # We assume 1 string argument for now.
        arg_value = frame.subject.get("qid", "")
        if arg_value:
             return pgf.Expr(fname, [pgf.readExpr(f'"{arg_value}"')])
        
        # Fallback to 0-arg if subject was empty dict
        return pgf.Expr(fname, [])

    async def get_supported_languages(self) -> List[str]:
        if not self.grammar:
            return []
        return [name[-3:].lower() for name in self.grammar.languages.keys()]

    async def reload(self) -> None:
        logger.info("gf_reloading_started")
        self._load_grammar()

    async def health_check(self) -> bool:
        return self.grammar is not None