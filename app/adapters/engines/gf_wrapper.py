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

try:
    from app.core.ports.grammar_engine import IGrammarEngine
except ImportError:
    class IGrammarEngine: pass

from app.core.domain.models import Sentence
from app.core.domain.frame import BioFrame
from app.core.domain.exceptions import LanguageNotFoundError, DomainError
from app.shared.config import settings
from app.shared.lexicon import lexicon

logger = structlog.get_logger()

# [FIX] Class name standardized to GFGrammarEngine
class GFGrammarEngine(IGrammarEngine):
    """
    Primary Grammar Engine using the compiled PGF binary.
    Supports Dual-Path: Strict BioFrame and Prototype UniversalNode.
    """

    def __init__(self, lib_path: str = None):
        self.pgf_path = getattr(settings, "PGF_PATH", None) or getattr(settings, "AW_PGF_PATH", "gf/AbstractWiki.pgf")
        self.grammar: Optional[Any] = None 
        self.inventory: Dict[str, Any] = {}
        self.iso_map: Dict[str, str] = {} 
        
        self._load_inventory()
        self._load_iso_config()
        self._load_grammar()

    def _load_inventory(self):
        try:
            candidates = []
            if settings and hasattr(settings, 'FILESYSTEM_REPO_PATH'):
                repo_root = Path(settings.FILESYSTEM_REPO_PATH)
                candidates.append(repo_root / "data" / "indices" / "rgl_inventory.json")
            
            candidates.append(Path(__file__).resolve().parents[3] / "data" / "indices" / "rgl_inventory.json")

            inventory_path = None
            for p in candidates:
                if p.exists():
                    inventory_path = p
                    break
            
            if inventory_path:
                with open(inventory_path, "r") as f:
                    data = json.load(f)
                    self.inventory = data.get("languages", {})
        except Exception:
            pass

    def _load_iso_config(self):
        try:
            candidates = []
            if settings and hasattr(settings, 'FILESYSTEM_REPO_PATH'):
                repo_root = Path(settings.FILESYSTEM_REPO_PATH)
                candidates.append(repo_root / "data" / "config" / "iso_to_wiki.json")
                candidates.append(repo_root / "config" / "iso_to_wiki.json")

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
                
                self.iso_map = {}
                for code, value in raw_data.items():
                    if isinstance(value, dict):
                        suffix = value.get("wiki")
                        if suffix: self.iso_map[code] = suffix
                    elif isinstance(value, str):
                        clean_val = value.replace("Wiki", "")
                        self.iso_map[code] = clean_val
        except Exception:
            pass

    def _load_grammar(self):
        if not pgf: return
        path = Path(self.pgf_path)
        if path.exists():
            try:
                self.grammar = pgf.readPGF(str(path))
            except Exception as e:
                logger.error("gf_load_failed", error=str(e))

    def parse(self, sentence: str, language: str):
        if not self.grammar: return []
        if language not in self.grammar.languages:
            concrete = self._resolve_concrete_name(language)
            if not concrete: return []
            language = concrete
        concrete_grammar = self.grammar.languages[language]
        try:
            return concrete_grammar.parse(sentence)
        except Exception:
            return []

    def linearize(self, expr: Any, language: str) -> str:
        if not self.grammar: return "<GF Runtime Not Loaded>"
        if language not in self.grammar.languages:
            concrete = self._resolve_concrete_name(language)
            if not concrete: return f"<Language '{language}' not found>"
            language = concrete
        concrete_grammar = self.grammar.languages[language]
        if isinstance(expr, str):
            try:
                expr_obj = pgf.readExpr(expr)
            except Exception as e:
                return f"<LinearizeError: {e}>"
        else:
            expr_obj = expr
        try:
            return concrete_grammar.linearize(expr_obj)
        except Exception as e:
            return f"<LinearizeError: {e}>"

    def _resolve_concrete_name(self, lang_code: str) -> Optional[str]:
        if not self.grammar: return None
        iso_clean = lang_code.lower().strip()
        rgl_suffix = self.iso_map.get(iso_clean)
        if rgl_suffix:
            candidate = f"Wiki{rgl_suffix}"
            if candidate in self.grammar.languages: return candidate
        if len(iso_clean) == 3:
            candidate = f"Wiki{iso_clean.capitalize()}"
            if candidate in self.grammar.languages: return candidate
        return None

    def _convert_to_gf_ast(self, node: Any, lang_code: str) -> str:
        if isinstance(node, BioFrame):
            name = node.name.replace('"', '\\"')
            s_expr = f'(mkEntity (mkPN "{name}"))'
            prof = getattr(node, "profession", None)
            p_expr = f'(lexProf (mkN "{prof}"))' if prof else '(lexProf (mkN "person"))'
            return f"mkBioProf {s_expr} {p_expr}"
        if isinstance(node, dict):
            func = node.get("function")
            if not func: return ""
            args = node.get("args", [])
            processed = [self._convert_to_gf_ast(a, lang_code) for a in args]
            args_str = " ".join([f"({a})" for a in processed])
            return f"{func} {args_str}"
        return f'"{str(node)}"'

    async def get_supported_languages(self) -> List[str]:
        if not self.grammar: return []
        return list(self.grammar.languages.keys())

    async def reload(self) -> None:
        self._load_grammar()
        self._load_inventory()
        self._load_iso_config()

    async def health_check(self) -> bool:
        return self.grammar is not None