# app\adapters\engines\gf_engine.py
import os
import json
import subprocess
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import structlog
import pgf # GF Python Bindings

from app.core.domain.models import Frame, Sentence
from app.core.domain.exceptions import LanguageNotReadyError, DomainError, ExternalServiceError
from app.core.ports.grammar_engine import IGrammarEngine
from app.shared.config import settings

logger = structlog.get_logger()

# -----------------------------------------------------------------------------
# GF Configuration
# -----------------------------------------------------------------------------
PGF_FILE = os.path.join(settings.GF_DIR, "Wiki.pgf") # Assuming settings has GF_DIR set
GF_TIMEOUT_SECONDS = 30
GF_BUILD_PATH = settings.GF_RGL_PATH # Path string containing RGL dependencies

# Exceptions we will retry on (e.g., transient network/GF errors)
RETRYABLE_EXCEPTIONS = (ExternalServiceError, subprocess.TimeoutExpired)

class GFEngine(IGrammarEngine):
    """
    Adapter implementation for IGrammarEngine using the Grammatical Framework (GF)
    C++ library via the Python 'pgf' bindings.
    
    This layer handles communication with the external GF toolchain.
    """

    def __init__(self):
        self._pgf = self._load_pgf()
        self._supported_languages = self._get_supported_languages()
        
    def _load_pgf(self) -> Optional[pgf.PGF]:
        """Loads the master PGF file (Wiki.pgf) into memory."""
        if not os.path.exists(PGF_FILE):
            logger.error("pgf_file_missing", path=PGF_FILE)
            return None
        
        try:
            pgf_grammar = pgf.readPGF(PGF_FILE)
            logger.info("pgf_loaded", path=PGF_FILE, languages=len(pgf_grammar.languages))
            return pgf_grammar
        except Exception as e:
            logger.error("pgf_load_failed", error=str(e))
            return None

    def _get_supported_languages(self) -> set[str]:
        """Extracts the list of supported languages from the PGF file."""
        if self._pgf:
            # We assume concrete syntaxes are named like WikiEng, WikiFra, etc.
            # We strip the 'Wiki' prefix for the ISO code.
            return {name.replace("Wiki", "") for name in self._pgf.languages.keys()}
        return set()

    def is_language_ready(self, lang_code: str) -> bool:
        """Checks if the required concrete syntax is loaded in the PGF."""
        # GF names are typically WikiEng, WikiFra (TitleCase of 3-letter code)
        gf_lang_name = f"Wiki{lang_code.capitalize()}"
        return self._pgf is not None and gf_lang_name in self._pgf.languages

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True
    )
    async def generate(self, lang_code: str, frame: Frame) -> Sentence:
        """
        Converts the semantic Frame into text using the GF engine.
        """
        if not self._pgf:
            raise ExternalServiceError("GF Engine is not initialized. PGF file missing or corrupt.")
            
        gf_lang_name = f"Wiki{lang_code.capitalize()}"

        if gf_lang_name not in self._pgf.languages:
            raise LanguageNotReadyError(f"Language '{lang_code}' not found or not compiled in Wiki.pgf.")

        # 1. Map Frame to Abstract Syntax Tree (AST)
        # This is the crucial domain-to-adapter translation step.
        # We assume a helper function in a 'mapper' module handles this.
        try:
            # Note: This is a placeholder. Real implementation needs a large mapping layer.
            ast_string = self._map_frame_to_ast(frame)
            if not ast_string:
                raise DomainError(f"Frame mapping failed for type: {frame.frame_type}")
                
            ast_expr = pgf.readExpr(ast_string)
            
        except Exception as e:
            logger.error("ast_mapping_failed", frame_type=frame.frame_type, error=str(e))
            raise DomainError(f"Failed to convert frame to AST: {str(e)}")

        # 2. Linearization
        concrete_syntax = self._pgf.languages[gf_lang_name]
        
        try:
            # Linearize the AST to the target language string
            text = concrete_syntax.linearize(ast_expr)
            
            # 3. Post-processing
            return Sentence(
                text=text,
                lang_code=lang_code,
                source_engine="gf"
            )
        except pgf.ParseError as e:
            logger.error("gf_linearization_failed", lang=lang_code, ast=ast_string, error=str(e))
            raise DomainError(f"GF Linearization failed (ParseError): {str(e)}")
        except Exception as e:
            logger.error("gf_runtime_error", lang=lang_code, error=str(e))
            raise ExternalServiceError(f"GF Runtime Error during linearization: {str(e)}")

    def _map_frame_to_ast(self, frame: Frame) -> Optional[str]:
        """
        [PLACEHOLDER] Maps a Pydantic Frame object into a GF Abstract Syntax Tree string.
        
        A full implementation would involve:
        1. A Construction selector based on frame.frame_type.
        2. Mapping frame properties (profession, name) to GF Abstract Functions (e.g., mkCN, mkNP).
        """
        if frame.frame_type == "bio":
            # Example: Generate AST for "Marie Curie is a Polish physicist."
            # The actual AST would be complex, involving mkSentence, mkCl, mkNP, etc.
            # Using a simplified AST that must exist in Wiki.gf:
            
            # Fallback to a core concept for testing if no specific logic exists
            concept = frame.subject.get("name", "John")
            return f"SimpNP {concept}_N" # Requires John_N, SimpNP to be abstract functions
            
        return None

    async def health_check(self) -> bool:
        """
        Verifies the engine is initialized and the PGF file is accessible.
        """
        is_ready = self._pgf is not None and self._supported_languages
        if not is_ready:
            logger.warning("gf_health_check_failed", reason="PGF not loaded or no languages found")
        
        # In a robust scenario, we might also run a dummy linearization (e.g., linearize "SimpNP apple_N")
        # to ensure the GF binary itself is callable.
        
        return is_ready