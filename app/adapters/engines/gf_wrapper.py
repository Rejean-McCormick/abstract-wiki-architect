# app\adapters\engines\gf_wrapper.py
import sys
import structlog
from typing import List, Optional
from pathlib import Path

# Try importing the GF runtime (pgf). 
# This is installed in the Docker container but might be missing locally.
try:
    import pgf
except ImportError:
    pgf = None

from app.core.ports.grammar_engine import IGrammarEngine
from app.core.domain.models import Frame, Sentence
from app.core.domain.exceptions import (
    LanguageNotFoundError, 
    DomainError, 
    GrammarCompilationError
)
from app.shared.config import settings

logger = structlog.get_logger()

class GFGrammarEngine(IGrammarEngine):
    """
    Primary Grammar Engine using the compiled PGF binary.
    
    It maps the generic 'Frame' entity into a GF 'Expr' (Abstract Syntax Tree)
    and then linearizes it using the underlying C-runtime for maximum speed
    and linguistic correctness.
    """

    def __init__(self):
        self.pgf_path = settings.AW_PGF_PATH
        self.grammar: Optional[pgf.PGF] = None
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
                logger.info("gf_grammar_loaded", path=str(path), languages=list(self.grammar.languages.keys()))
            except Exception as e:
                logger.error("gf_load_failed", error=str(e))
                # We don't crash start-up; we just won't be able to generate until fixed.
        else:
            logger.warning("gf_pgf_not_found", path=str(path))

    async def generate(self, lang_code: str, frame: Frame) -> Sentence:
        """
        1. Look up Concrete Grammar (e.g., 'WikiFra' for 'fra').
        2. Convert Frame -> PGF Expression.
        3. Linearize Expression -> Text.
        """
        if not self.grammar:
            raise DomainError("GF Runtime is not loaded.")

        # 1. Resolve Concrete Language
        # The PGF usually names languages like 'WikiEng', 'WikiFra'.
        # We need a mapping strategy. For now, we try 'Wiki' + TitleCase(lang_code) or ISO match.
        conc_name = self._resolve_concrete_name(lang_code)
        if not conc_name:
            raise LanguageNotFoundError(lang_code)
        
        concrete = self.grammar.languages[conc_name]

        # 2. Construct AST (Abstract Syntax Tree)
        # This transforms the generic JSON Frame into a strictly typed GF Tree.
        try:
            expr = self._build_expr(frame)
        except Exception as e:
            logger.error("gf_ast_construction_failed", frame=frame.frame_type, error=str(e))
            raise DomainError(f"Failed to construct grammar tree: {str(e)}")

        # 3. Linearize
        try:
            # linearize returns a string. handling exceptions from C-level.
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
        # Heuristic: The PGF usually contains names like 'WikiEng', 'WikiChi'.
        # We search for the suffix.
        target_suffix = lang_code.capitalize() # 'fra' -> 'Fra' (Note: ISO 3 letter codes match RGL conventions usually)
        
        # 1. Direct Lookup if naming convention is strict
        candidate = f"Wiki{target_suffix}"
        if candidate in self.grammar.languages:
            return candidate

        # 2. Search (Slower)
        for name in self.grammar.languages.keys():
            if name.endswith(target_suffix):
                return name
        
        return None

    def _build_expr(self, frame: Frame) -> pgf.Expr:
        """
        Converts the generic Frame into a PGF Expression.
        
        Example:
        Frame(type="Bio", subject={"qid": "Q42"}) 
        -> mkBio (mkPerson "Q42")
        """
        # This is a simplifed mapper. In a real system, this would be recursive
        # and use the type signature of the grammar to know which functions to call.
        
        # We assume the Frame 'type' corresponds to a function in the Abstract Syntax.
        function_name = f"mk{frame.frame_type.capitalize()}" 
        
        # We check if the function exists in the grammar
        if function_name not in self.grammar.functions:
            # Fallback or error
            raise DomainError(f"Grammar function '{function_name}' not found.")

        # Construct Arguments
        # This requires knowledge of the function signature.
        # For this example, we assume we pass the subject QID as a string literal.
        qid = frame.subject.get("qid", "Q0")
        
        # In PGF python: pgf.readExpr('mkBio (mkPerson "Q42")') is easiest for simple stuff.
        # Or constructing via pgf.Expr(fun, [args...])
        
        # Simplified logic:
        # We assume the grammar has a wrapper function that takes a string string.
        # Real impl requires sophisticated argument mapping.
        
        # Helper: Create a string literal expression
        arg_str = pgf.readExpr(f'"{qid}"') 
        
        # Create the function call: mkBio "Q42"
        # (Assuming mkBio takes a String in this simplified grammar)
        expr = pgf.Expr(function_name, [arg_str])
        
        return expr

    async def get_supported_languages(self) -> List[str]:
        if not self.grammar:
            return []
        # Return ISO codes derived from concrete names
        return [name[-3:].lower() for name in self.grammar.languages.keys()]

    async def reload(self) -> None:
        """Hot-reloads the PGF file."""
        logger.info("gf_reloading_started")
        self._load_grammar()

    async def health_check(self) -> bool:
        return self.grammar is not None