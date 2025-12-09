"""
ROUTER
======

Central orchestration for the low-level NLG system.

Responsibilities
----------------
- Load language profiles (language_profiles/profiles.json).
- For a given language code, decide which **morphology family** to use.
- Instantiate the appropriate morphology module for that family.
- For a given construction ID, import and call the right construction function.
- Provide entrypoints: render(...) and render_bio(...).

ROBUSTNESS UPDATE:
- Fallbacks to 'default' profile if a language is missing configuration.
- Fallbacks to empty language cards if data/ files are missing.
"""

from __future__ import annotations

import importlib
import json
import os
import logging
from typing import Any, Callable, Dict, Optional

# Logger setup
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry: language family -> (module path, morphology class name)
# ---------------------------------------------------------------------------

MORPHOLOGY_CLASS_REGISTRY: Dict[str, tuple[str, str]] = {
    "romance": ("morphology.romance", "RomanceMorphology"),
    "agglutinative": ("morphology.agglutinative", "AgglutinativeMorphology"),
    "slavic": ("morphology.slavic", "SlavicMorphology"),
    "germanic": ("morphology.germanic", "GermanicMorphology"),
    "bantu": ("morphology.bantu", "BantuMorphology"),
    "isolating": ("morphology.isolating", "IsolatingMorphology"),
    "japonic": ("morphology.japonic", "JaponicMorphology"),
    "koreanic": ("morphology.koreanic", "KoreanicMorphology"),
    "semitic": ("morphology.semitic", "SemiticMorphology"),
    "polysynthetic": ("morphology.polysynthetic", "PolysyntheticMorphology"),
    "dravidian": ("morphology.dravidian", "DravidianMorphology"),
    "austronesian": ("morphology.austronesian", "AustronesianMorphology"),
    "celtic": ("morphology.celtic", "CelticMorphology"),
    "indo_aryan": ("morphology.indo_aryan", "IndoAryanMorphology"),
    "iranic": ("morphology.iranic", "IranicMorphology"),
    # Fallback family for pidgin/factory languages
    "analytic": ("morphology.isolating", "IsolatingMorphology"), 
}


# ---------------------------------------------------------------------------
# Registry: construction id -> (module path, function name)
# ---------------------------------------------------------------------------

CONSTRUCTION_REGISTRY: Dict[str, tuple[str, str]] = {
    "possession_existential": ("constructions.possession_existential", "realize_possession_existential"),
    "relative_clause_object_gap": ("constructions.relative_clause_object_gap", "realize_relative_clause_object_gap"),
    "coordination_clauses": ("constructions.coordination_clauses", "realize_coordination_clauses"),
    # Core construction types:
    "copula_equative_simple": ("constructions.copula_equative_simple", "realize"),
    "copula_equative_classification": ("constructions.copula_equative_classification", "realize_equative_classification"),
    "copula_attributive_adj": ("constructions.copula_attributive_adj", "realize_attributive_adj"),
    "copula_attributive_np": ("constructions.copula_attributive_np", "render"),
    "copula_locative": ("constructions.copula_locative", "render"),
    "copula_existential": ("constructions.copula_existential", "realize"),
    "possession_have": ("constructions.possession_have", "realize"),
    "relative_clause_subject_gap": ("constructions.relative_clause_subject_gap", "realize"),
    "intransitive_event": ("constructions.intransitive_event", "realize"),
    "transitive_event": ("constructions.transitive_event", "realize"),
    "ditransitive_event": ("constructions.ditransitive_event", "realize_ditransitive_event"),
    "passive_event": ("constructions.passive_event", "realize"),
    "causative_event": ("constructions.causative_event", "realize"),
    "topic_comment_copular": ("constructions.topic_comment_copular", "realize"),
    "topic_comment_eventive": ("constructions.topic_comment_eventive", "realize_topic_comment_eventive"),
    "apposition_np": ("constructions.apposition_np", "render"),
    "comparative_superlative": ("constructions.comparative_superlative", "realize"),
}


# ---------------------------------------------------------------------------
# Language profiles loader
# ---------------------------------------------------------------------------

DEFAULT_PROFILE = {
    "language_code": "default",
    "morphology_family": "analytic", # Safe fallback
    "word_order": "SVO",
    "default_style": "formal"
}

def _default_profiles_path() -> str:
    """Return the absolute path to language_profiles/profiles.json."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "language_profiles", "profiles.json")


def _load_profiles(path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Load language profiles from JSON file."""
    profiles_path = path or _default_profiles_path()
    if not os.path.exists(profiles_path):
        logger.warning(f"Language profiles file not found: {profiles_path}. Using empty registry.")
        return {}

    try:
        with open(profiles_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in profiles: {e}")
        return {}

    if not isinstance(data, dict):
        return {}

    profiles: Dict[str, Dict[str, Any]] = {}
    for code, prof in data.items():
        if isinstance(code, str) and isinstance(prof, dict):
            profiles[code] = prof

    return profiles


# ---------------------------------------------------------------------------
# NLGRouter
# ---------------------------------------------------------------------------


class NLGRouter:
    """
    Router for language-specific NLG at the construction level.
    """

    def __init__(
        self,
        profiles_path: Optional[str] = None,
    ) -> None:
        self._profiles_path = profiles_path
        self._profiles: Dict[str, Dict[str, Any]] = _load_profiles(self._profiles_path)

        # Cache morphology instances per language code
        self._morph_cache: Dict[str, Any] = {}

        # Cache imported construction callables: (module_path, func_name) -> callable
        self._construction_cache: Dict[tuple[str, str], Callable[..., str]] = {}

    # --------------------- language profile ---------------------

    def get_language_profile(self, lang_code: str) -> Dict[str, Any]:
        """
        Return the language profile dict for a given language code.
        [ROBUST] Returns DEFAULT_PROFILE if specific lang is missing.
        """
        if not isinstance(lang_code, str):
            raise TypeError("lang_code must be a string")

        if lang_code in self._profiles:
            return self._profiles[lang_code]
        
        # Fallback for Factory Languages (Tier 3) or unconfigured langs
        logger.warning(f"[Router] No profile found for '{lang_code}'. Using Default SVO Profile.")
        return DEFAULT_PROFILE

    # --------------------- morphology ---------------------------

    def _resolve_morphology_family(self, profile: Dict[str, Any]) -> str:
        """
        Decide which morphology family to use for a profile.
        """
        override = profile.get("morphology_family_override")
        if isinstance(override, str) and override in MORPHOLOGY_CLASS_REGISTRY:
            return override

        morph_family = profile.get("morphology_family")
        if isinstance(morph_family, str) and morph_family in MORPHOLOGY_CLASS_REGISTRY:
            return morph_family

        legacy_family = profile.get("family")
        if (
            isinstance(legacy_family, str)
            and legacy_family in MORPHOLOGY_CLASS_REGISTRY
        ):
            return legacy_family

        # Fallback if profile is malformed but exists
        logger.warning(f"Could not resolve family for profile. Defaulting to 'analytic'.")
        return "analytic"

    def _build_morphology(self, lang_code: str) -> Any:
        """Instantiate the morphology object for the given language."""
        profile = self.get_language_profile(lang_code)
        family = self._resolve_morphology_family(profile)

        module_path, class_name = MORPHOLOGY_CLASS_REGISTRY[family]

        try:
            module = importlib.import_module(module_path)
            morph_cls = getattr(module, class_name)
            return morph_cls(profile)
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load morphology {class_name} from {module_path}: {e}")
            # Fallback to Isolating (safest)
            from morphology.isolating import IsolatingMorphology
            return IsolatingMorphology(profile)

    def get_morphology(self, lang_code: str) -> Any:
        """Return a cached morphology API instance for the language."""
        if lang_code in self._morph_cache:
            return self._morph_cache[lang_code]

        morph = self._build_morphology(lang_code)
        self._morph_cache[lang_code] = morph
        return morph

    # --------------------- constructions ------------------------

    def _load_construction_callable(
        self,
        module_path: str,
        func_name: str,
    ) -> Callable[..., str]:
        """Import and cache a construction function."""
        key = (module_path, func_name)
        if key in self._construction_cache:
            return self._construction_cache[key]

        try:
            module = importlib.import_module(module_path)
            fn = getattr(module, func_name)
        except (ImportError, AttributeError) as e:
            # If construction missing, return a dummy lambda to prevent crash
            logger.error(f"Construction missing: {module_path}.{func_name}. Error: {e}")
            return lambda *args, **kwargs: "[[CONSTRUCTION_ERROR]]"

        if not callable(fn):
            raise TypeError(f"{module_path}.{func_name} is not callable")

        self._construction_cache[key] = fn
        return fn

    def get_construction_callable(
        self,
        construction_id: str,
    ) -> Callable[..., str]:
        """Resolve a construction ID to a callable."""
        if construction_id not in CONSTRUCTION_REGISTRY:
            logger.error(f"Unknown construction_id: {construction_id!r}")
            return lambda *args, **kwargs: f"[[UNKNOWN: {construction_id}]]"

        module_path, func_name = CONSTRUCTION_REGISTRY[construction_id]
        return self._load_construction_callable(module_path, func_name)

    # --------------------- public API ---------------------------

    def render(
        self,
        construction_id: str,
        slots: Any,
        lang_code: str,
    ) -> str:
        """Render a sentence for the given construction, slots and language."""
        lang_profile = self.get_language_profile(lang_code)
        morph_api = self.get_morphology(lang_code)

        construction_fn = self.get_construction_callable(construction_id)
        try:
            return construction_fn(slots, lang_profile, morph_api)
        except Exception as e:
            logger.error(f"Render error in {construction_id} for {lang_code}: {e}")
            return f"[[RENDER_ERROR: {e}]]"


# ---------------------------------------------------------------------------
# Convenience singleton + top-level helpers
# ---------------------------------------------------------------------------

_default_router: Optional[NLGRouter] = None


def get_router() -> NLGRouter:
    """Return a process-global NLGRouter singleton."""
    global _default_router
    if _default_router is None:
        _default_router = NLGRouter()
    return _default_router


def get_language_profile(lang_code: str) -> Dict[str, Any]:
    return get_router().get_language_profile(lang_code)


def get_morphology(lang_code: str) -> Any:
    return get_router().get_morphology(lang_code)


def render(
    construction_id: str,
    slots: Any,
    lang_code: str,
) -> str:
    router = get_router()
    return router.render(construction_id, slots, lang_code)


# ---------------------------------------------------------------------------
# High-Level Biography Helper (Bridge to Engines)
# ---------------------------------------------------------------------------

_LANG_CARD_CACHE: Dict[tuple[str, str], Dict[str, Any]] = {}


def _load_language_card(family: str, lang_code: str) -> Dict[str, Any]:
    """
    Load the language card from data/<family>/<lang_code>.json.
    [ROBUST] Returns empty dict if file not found.
    """
    key = (family, lang_code)
    if key in _LANG_CARD_CACHE:
        return _LANG_CARD_CACHE[key]

    project_root = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(project_root, "data", family, f"{lang_code}.json")

    if not os.path.exists(config_path):
        # [FIX] Do not crash. Return empty card.
        logger.warning(f"Language card not found: {config_path}. Using empty config.")
        _LANG_CARD_CACHE[key] = {}
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse language card {config_path}: {e}")
        return {}

    if not isinstance(config, dict):
        return {}

    _LANG_CARD_CACHE[key] = config
    return config


def render_bio(
    name: str,
    gender: str,
    profession_lemma: str,
    nationality_lemma: str,
    lang_code: str,
) -> str:
    """
    High-level helper to render a biography sentence.
    """
    router = get_router()
    profile = router.get_language_profile(lang_code)

    family: Optional[str] = profile.get("morphology_family") or profile.get("family")
    if not family:
        family = "analytic" # Default

    # 1. Load the Language Card (Config) - Now Safe
    lang_config = _load_language_card(family, lang_code)

    # 2. Import the Engine Module
    engine_module_name = f"engines.{family}"
    
    # [FIX] Handle missing engine modules (e.g. engines.analytic might not exist)
    try:
        engine_module = importlib.import_module(engine_module_name)
    except ImportError:
        # Fallback to a generic engine if specific family engine is missing
        try:
            # Try loading a generic 'engines.isolating' or similar if available
            # Or just return a simple formatted string as ultimate fallback
            logger.warning(f"Engine {engine_module_name} not found. Using fallback.")
            return f"{name} IS {profession_lemma} . {name} IS {nationality_lemma} ."
        except:
            return f"{name} {profession_lemma} {nationality_lemma}"

    # 3. Call the engine's render_bio
    if not hasattr(engine_module, "render_bio"):
        return f"{name} IS {profession_lemma} (Engine Not Implemented)"

    try:
        return engine_module.render_bio(
            name,
            gender,
            profession_lemma,
            nationality_lemma,
            lang_config,
        )
    except Exception as e:
        logger.error(f"Error in engine render_bio: {e}")
        return f"{name} IS {profession_lemma}"


# Alias for universal test runner compatibility
render_biography = render_bio


__all__ = [
    "NLGRouter",
    "MORPHOLOGY_CLASS_REGISTRY",
    "CONSTRUCTION_REGISTRY",
    "get_router",
    "get_language_profile",
    "get_morphology",
    "render",
    "render_bio",
    "render_biography",
]