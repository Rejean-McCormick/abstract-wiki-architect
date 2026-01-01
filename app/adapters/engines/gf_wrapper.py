# app/adapters/engines/gf_wrapper.py
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
            # [FIX] Use configured repo path instead of fragile CWD
            # Robust Path Resolution logic
            candidates = []

            # 1. Highest Priority: Explicit environment variable/settings override
            if settings and hasattr(settings, 'FILESYSTEM_REPO_PATH'):
                repo_root = Path(settings.FILESYSTEM_REPO_PATH)
                candidates.append(repo_root / "data" / "indices" / "rgl_inventory.json")

            # 2. Fallback: Relative to this file (less robust but safe default)
            candidates.append(Path(__file__).parent.parent.parent.parent / "data" / "indices" / "rgl_inventory.json")

            inventory_path = None
            for p in candidates:
                if p.exists():
                    inventory_path = p
                    break
            
            if inventory_path and inventory_path.exists():
                with open(inventory_path, "r") as f:
                    data = json.load(f)
                    self.inventory = data.get("languages", {})
                logger.info("gf_inventory_loaded", count=len(self.inventory))
            else:
                 logger.warning("gf_inventory_missing", path=str(inventory_path))

        except Exception as e:
            logger.warning("gf_inventory_error", error=str(e))

    def _load_iso_config(self):
        """
        Loads the 'Rosetta Stone' map to bridge ISO codes (en) to RGL suffixes (Eng).
        """
        try:
            # [FIX] Robust Path Resolution logic for config/iso_to_wiki.json
            candidates = []

            # 1. Highest Priority: Explicit environment variable/settings override
            if settings and hasattr(settings, 'FILESYSTEM_REPO_PATH'):
                repo_root = Path(settings.FILESYSTEM_REPO_PATH)
                candidates.append(repo_root / "data" / "config" / "iso_to_wiki.json")
                candidates.append(repo_root / "config" / "iso_to_wiki.json")

            # 2. Relative to this file's location (app/adapters/engines/gf_wrapper.py -> root)
            # This is reliable because the file structure is static within the package
            # Walk up 4 levels: app/adapters/engines/gf_wrapper.py -> app/adapters/engines/ -> app/adapters/ -> app/ -> root/
            project_root = Path(__file__).resolve().parents[3]
            candidates.append(project_root / "data" / "config" / "iso_to_wiki.json")
            candidates.append(project_root / "config" / "iso_to_wiki.json")

            config_path = None
            for p in candidates:
                if p.exists():
                    config_path = p
                    break
            
            if config_path:
                with open(config_path, "r") as f:
                    raw_data = json.load(f)
                
                # Normalize data into self.iso_map (Dict[str, str])
                self.iso_map = {}
                for code, value in raw_data.items():
                    if isinstance(value, dict):
                        # v2.0 Rich Object: {"wiki": "Eng", "tier": 1}
                        suffix = value.get("wiki")
                        if suffix:
                            self.iso_map[code] = suffix
                    elif isinstance(value, str):
                        # v1.0 Legacy: "WikiEng" or "Eng"
                        # Strip "Wiki" if present to normalize to Suffix only
                        clean_val = value.replace("Wiki", "")
                        self.iso_map[code] = clean_val
                        
                logger.info("gf_config_loaded", mappings=len(self.iso_map))
            else:
                logger.warning("gf_config_missing", searched_paths=[str(c) for c in candidates])
        except Exception as e:
            logger.error("gf_config_error", error=str(e))

    def _load_grammar(self):
        """
        Loads the PGF binary and applies the 'Everything Matrix' safety filter.
        """
        if not pgf:
            logger.warning("gf_runtime_missing", msg="pgf library not installed.")
            return

        path = Path(self.pgf_path)
        if path.exists():
            try:
                # 1. Load the Binary (All languages linked)
                self.grammar = pgf.readPGF(str(path))
                
                # 2. v2.1: Enforce Runnable Verdict (The Safety Filter)
                # We check the Matrix to identify "Zombie Languages" (linked but empty data)
                # and remove them from the runtime before the application sees them.
                
                # Robust path resolution for Matrix
                candidates = []
                if settings and hasattr(settings, 'FILESYSTEM_REPO_PATH'):
                     candidates.append(Path(settings.FILESYSTEM_REPO_PATH) / "data" / "indices" / "everything_matrix.json")
                candidates.append(Path(__file__).resolve().parents[3] / "data" / "indices" / "everything_matrix.json")
                
                matrix_path = None
                for p in candidates:
                    if p.exists():
                        matrix_path = p
                        break
                
                if matrix_path and matrix_path.exists():
                    try:
                        with open(matrix_path, "r") as f:
                            matrix = json.load(f)
                        
                        # Iterate a copy of keys since we might delete
                        for lang_name in list(self.grammar.languages.keys()):
                            # Heuristic: Map 'WikiFra' -> 'fra' (last 3 chars, lower)
                            iso_code = lang_name[-3:].lower()
                            
                            lang_data = matrix.get("languages", {}).get(iso_code)
                            if lang_data:
                                verdict = lang_data.get("verdict", {})
                                is_runnable = verdict.get("runnable", True)
                                
                                if not is_runnable:
                                    logger.warning("runtime_purging_zombie_language", 
                                                 lang=lang_name, 
                                                 reason="Matrix verdict.runnable=False")
                                    # Active Purge: Remove from C-Runtime dictionary
                                    del self.grammar.languages[lang_name]
                                    
                    except Exception as e:
                        logger.error("runtime_matrix_filter_failed", error=str(e))
                else:
                    logger.warning("runtime_matrix_missing", path=str(matrix_path))

                logger.info("gf_grammar_loaded", path=str(path), active_languages=list(self.grammar.languages.keys()))
                
            except Exception as e:
                logger.error("gf_load_failed", error=str(e))
        else:
            logger.error("gf_file_not_found", path=str(path))

    async def generate(self, lang_code: str, frame: Any) -> Sentence:
        if not self.grammar:
            raise DomainError("GF Runtime is not loaded.")

        # --- THE BRIDGE ---
        # Converts 'en' -> 'WikiEng' just in time.
        conc_name = self._resolve_concrete_name(lang_code)
        
        if not conc_name:
            avail = list(self.grammar.languages.keys())
            raise LanguageNotFoundError(f"Language '{lang_code}' not found in PGF. Available: {len(avail)}")
        
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
        The Bridge Function.
        Resolves 'en' -> 'WikiEng' using the loaded map or heuristics.
        """
        iso_clean = lang_code.lower().strip()
        
        # 1. Lookup RGL Suffix from Config (The Correct Way)
        rgl_suffix = self.iso_map.get(iso_clean)
        if rgl_suffix:
            candidate = f"Wiki{rgl_suffix}"
            if candidate in self.grammar.languages:
                return candidate
            
        # 2. Legacy Support (The "Safety Net" for 'eng')
        # If the user passed 3 letters, assume they might mean the suffix directly
        if len(iso_clean) == 3:
            candidate = f"Wiki{iso_clean.capitalize()}"
            if candidate in self.grammar.languages:
                return candidate
                
        return None

    def _convert_to_gf_ast(self, node: Any, lang_code: str) -> str:
        # --- PATH 1: Handle Strict BioFrame (FLAT STRUCTURE) ---
        if isinstance(node, BioFrame):
            name = node.name
            
            # [FIX] Extraction Strategy for Pydantic v2
            # Pydantic may convert 'subject' to an Entity object OR a Dict depending on input.
            # We must handle both cases safely.
            def get_attr(obj, key):
                if isinstance(obj, dict):
                    return obj.get(key)
                return getattr(obj, key, None)

            # Resolve Profession
            prof = getattr(node, "profession", None)
            if not prof:
                prof = get_attr(node.subject, "profession")
            
            # Resolve Nationality
            nat = getattr(node, "nationality", None)
            if not nat:
                nat = get_attr(node.subject, "nationality")

            # Construct Entity (Subject)
            # Ensure safe string escaping
            safe_name = name.replace('"', '\\"')
            s_expr = f'(mkEntity (mkPN "{safe_name}"))'
            
            # Construct Profession
            # Heuristic: No spaces = likely a GF ID (physicist_N). Spaces = Raw String.
            if prof and " " not in prof:
                # Use Type Coercion: N -> Profession
                p_expr = f'(lexProf {prof})' 
            else:
                # Fallback: String -> Profession (Requires mkCN (mkN ...))
                # Assuming lexProf can handle a CN if defined loosely, or we use a constructor
                safe_prof = (prof or "").replace('"', '\\"')
                p_expr = f'(lexProf (mkN "{safe_prof}"))'

            # Construct Nationality & Dispatch Overload
            if nat:
                if " " not in nat:
                    n_expr = f'(lexNat {nat})'
                else:
                    safe_nat = nat.replace('"', '\\"')
                    # [FIX] Use mkA (Make Adjective) for nationalities, not mkN (Make Noun)
                    # The function lexNat : A -> Nationality expects an Adjective.
                    # Passing mkN (Noun) causes a "found CN, expected A" type error.
                    n_expr = f'(lexNat (mkA "{safe_nat}"))' 
                
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