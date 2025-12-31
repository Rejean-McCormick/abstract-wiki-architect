import sys
import os
import json
import structlog
from typing import List, Optional, Any, Dict
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
from app.shared.lexicon import lexicon

logger = structlog.get_logger()

class GFGrammarEngine(IGrammarEngine):
    """
    Primary Grammar Engine using the compiled PGF binary.
    Supports Dual-Path: Strict BioFrame and Prototype UniversalNode.
    """

    def __init__(self, lib_path: str = None):
        # Fallback to AW_PGF_PATH if PGF_PATH isn't set
        self.pgf_path = getattr(settings, "PGF_PATH", None) or getattr(settings, "AW_PGF_PATH", "gf/AbstractWiki.pgf")
        self.grammar: Optional[pgf.PGF] = None
        self.inventory: Dict[str, Any] = {}
        self.iso_map: Dict[str, str] = {} # Configuration Map: 'sw' -> 'Swa'
        
        # 1. Load Configurations
        self._load_inventory()
        self._load_iso_config()
        
        logger.debug(f"GFGrammarEngine initializing from: {self.pgf_path}")
        self._load_grammar()

    def _load_inventory(self):
        """Loads the dynamic registry of available languages from the indexer."""
        try:
            repo_root = Path(os.getcwd())
            inventory_path = repo_root / "data" / "indices" / "rgl_inventory.json"
            
            if inventory_path.exists():
                with open(inventory_path, "r") as f:
                    data = json.load(f)
                    self.inventory = data.get("languages", {})
                logger.info("gf_inventory_loaded", count=len(self.inventory))
        except Exception as e:
            logger.warning("gf_inventory_missing", error=str(e))

    def _load_iso_config(self):
        """
        Loads 'config/iso_to_wiki.json' to map ISO codes (en) to RGL suffixes (Eng).
        Handles both simple mappings {"en": "Eng"} and rich objects {"en": {"wiki": "Eng", ...}}.
        This replaces the hardcoded dictionary.
        """
        try:
            repo_root = Path(os.getcwd())
            config_path = repo_root / "config" / "iso_to_wiki.json"
            
            if config_path.exists():
                with open(config_path, "r") as f:
                    raw_data = json.load(f)
                
                # Normalize data into self.iso_map (Dict[str, str])
                self.iso_map = {}
                for code, value in raw_data.items():
                    if isinstance(value, dict):
                        # Extract 'wiki' suffix from rich object (v2.0 format)
                        suffix = value.get("wiki")
                        if suffix:
                            self.iso_map[code] = suffix
                    elif isinstance(value, str):
                        # Handle legacy string mapping (v1.0 format)
                        self.iso_map[code] = value
                        
                logger.info("gf_config_loaded", mappings=len(self.iso_map))
            else:
                logger.warning("gf_config_missing", path=str(config_path))
        except Exception as e:
            logger.error("gf_config_error", error=str(e))

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
            raise LanguageNotFoundError(f"Language {lang_code} not found in PGF. Available: {len(avail)}")
        
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
        Strategy: Config Map -> PGF Check -> Fallback
        """
        iso_clean = lang_code.lower().strip()
        
        # 1. Lookup RGL Suffix from Config (sw -> Swa)
        rgl_suffix = self.iso_map.get(iso_clean)
        
        if rgl_suffix:
            # Try strict RGL name (WikiSwa)
            candidate = f"Wiki{rgl_suffix}"
            if candidate in self.grammar.languages:
                return candidate
            
        # 2. Fallback: Direct Capitalization (Legacy/Safe Mode Support)
        # Your Safe Mode factory generates 'WikiSw' (not WikiSwa), so this catches that.
        if len(iso_clean) >= 2:
            candidate = f"Wiki{iso_clean.title()}"
            if candidate in self.grammar.languages:
                return candidate
                
        return None

    def _convert_to_gf_ast(self, node: Any, lang_code: str) -> str:
        # --- PATH 1: Handle Strict BioFrame (FLAT STRUCTURE) ---
        if isinstance(node, BioFrame):
            name = node.name
            prof = node.profession
            nat = node.nationality

            # Construct Entity (Subject)
            s_expr = f'(mkEntityStr "{name}")'
            
            # Construct Profession
            if prof and " " not in prof:
                p_expr = f'(strProf "{prof}")' 
            else:
                p_expr = f'(strProf "{prof}")'

            # Construct Nationality & Dispatch Overload
            if nat:
                n_expr = f'(strNat "{nat}")'
                return f"mkBioFull {s_expr} {p_expr} {n_expr}"
            else:
                return f"mkBioProf {s_expr} {p_expr}"

        # --- PATH 2: Handle Primitives (Strings/Ints) ---
        if isinstance(node, (str, int, float)):
            s_node = str(node)
            
            # Lookup in Lexicon (Zone B)
            entry = lexicon.lookup(s_node, lang_code)
            lemma = entry.lemma if entry else s_node
            
            # Escape quotes for GF string literals
            safe_lemma = lemma.replace('"', '\\"')
            return f'"{safe_lemma}"'

        # --- PATH 3: Handle Raw Dictionaries / UniversalNode ---
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
        return list(self.grammar.languages.keys())

    async def reload(self) -> None:
        self._load_grammar()
        self._load_inventory()
        self._load_iso_config()

    async def health_check(self) -> bool:
        return self.grammar is not None