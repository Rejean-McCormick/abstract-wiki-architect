"""
ROUTER
======

Central orchestration for the low-level NLG system.

This module is the main entry point used by higher-level bridges such as:

- `semantics.aw_bridge.render_from_z_call` (Wikifunctions / Abstract Wikipedia),
- any internal services that want to call a *construction* directly.

It does **not** expose the high-level frame-based API (`nlg.api`); that layer
is a separate, thin frontend. The router here focuses on:

Responsibilities
----------------
- Load language profiles (language_profiles/profiles.json).
- For a given language code, decide which **morphology family** to use.
- Instantiate the appropriate morphology module for that family.
- For a given construction ID, import and call the right construction function.
- Provide a simple entrypoint:

      render(construction_id, slots, lang_code) -> str

This router is **family-agnostic** at the construction level: it only cares
about which construction to call and which morphology module to bind to it.
All language-specific behavior lives in:

- language profile (syntax & construction options),
- morphology module (family-based),
- construction module (family-agnostic).

Expected environment
--------------------

1) language_profiles/profiles.json

   A JSON object mapping language codes to profiles, e.g.:

       {
         "ja": {
           "language_code": "ja",
           "morphology_family": "japonic",
           "basic_word_order": "SOV",
           "default_style": "formal",
           "possession_existential": { ... },
           "coordination_clauses": { ... },
           ...
        },
        "fr": {
          "language_code": "fr",
          "morphology_family": "romance",
          ...
        }
       }

   The canonical field is `morphology_family`. A legacy field `family`
   (with the same values) is also accepted for backwards compatibility.
   An optional `morphology_family_override` can force a different family
   for a particular language/profile if needed.

2) Morphology modules:

   Each family has a morphology module and a primary class, e.g.:

       morphology/romance.py       -> class RomanceMorphology
       morphology/agglutinative.py -> class AgglutinativeMorphology
       morphology/japonic.py       -> class JaponicMorphology
       ...

   The router instantiates them as:

       morph_cls(config_dict)
       morph_api = morph_cls(config_dict)

   where `config_dict` is the language profile for the target language.

3) Construction modules:

   Each construction module provides a `realize_*` function, e.g.:

       constructions/possession_existential.py
           -> realize_possession_existential(slots, lang_profile, morph_api)

       constructions/coordination_clauses.py
           -> realize_coordination_clauses(clauses, lang_profile, morph_api, ...)

   The router uses a registry from construction IDs to
   (module_path, function_name).

Extendibility
-------------

You can extend the registries below without changing router logic:

- add new morphology families to `MORPHOLOGY_CLASS_REGISTRY`,
- add new constructions to `CONSTRUCTION_REGISTRY`.

Higher-level layers (e.g. frame-based generation, discourse planning)
should call into this router via a thin abstraction, rather than poking
directly at morphology or constructions.
"""

from __future__ import annotations

import importlib
import json
import os
from typing import Any, Callable, Dict, Optional


# ---------------------------------------------------------------------------
# Registry: language family -> (module path, morphology class name)
# ---------------------------------------------------------------------------

MORPHOLOGY_CLASS_REGISTRY: Dict[str, tuple[str, str]] = {
    # family          module path                 class name
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
    # Add more families as needed
}


# ---------------------------------------------------------------------------
# Registry: construction id -> (module path, function name)
# ---------------------------------------------------------------------------

CONSTRUCTION_REGISTRY: Dict[str, tuple[str, str]] = {
    # id                          module path                                     function
    "possession_existential": (
        "constructions.possession_existential",
        "realize_possession_existential",
    ),
    "relative_clause_object_gap": (
        "constructions.relative_clause_object_gap",
        "realize_relative_clause_object_gap",
    ),
    "coordination_clauses": (
        "constructions.coordination_clauses",
        "realize_coordination_clauses",
    ),
    # Core construction types:
    "copula_equative_simple": (
        "constructions.copula_equative_simple",
        "realize",
    ),
    "copula_equative_classification": (
        "constructions.copula_equative_classification",
        "realize_equative_classification",
    ),
    "copula_attributive_adj": (
        "constructions.copula_attributive_adj",
        "realize_attributive_adj",
    ),
    "copula_attributive_np": (
        "constructions.copula_attributive_np",
        "render",
    ),
    "copula_locative": (
        "constructions.copula_locative",
        "render",
    ),
    "copula_existential": (
        "constructions.copula_existential",
        "realize",
    ),
    "possession_have": (
        "constructions.possession_have",
        "realize",
    ),
    "relative_clause_subject_gap": (
        "constructions.relative_clause_subject_gap",
        "realize",
    ),
    "intransitive_event": (
        "constructions.intransitive_event",
        "realize",
    ),
    "transitive_event": (
        "constructions.transitive_event",
        "realize",
    ),
    "ditransitive_event": (
        "constructions.ditransitive_event",
        "realize_ditransitive_event",
    ),
    "passive_event": (
        "constructions.passive_event",
        "realize",
    ),
    "causative_event": (
        "constructions.causative_event",
        "realize",
    ),
    "topic_comment_copular": (
        "constructions.topic_comment_copular",
        "realize",
    ),
    "topic_comment_eventive": (
        "constructions.topic_comment_eventive",
        "realize_topic_comment_eventive",
    ),
    "apposition_np": (
        "constructions.apposition_np",
        "render",
    ),
    "comparative_superlative": (
        "constructions.comparative_superlative",
        "realize",
    ),
}


# ---------------------------------------------------------------------------
# Language profiles loader
# ---------------------------------------------------------------------------


def _default_profiles_path() -> str:
    """Return the absolute path to language_profiles/profiles.json."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "language_profiles", "profiles.json")


def _load_profiles(path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Load language profiles from JSON file."""
    profiles_path = path or _default_profiles_path()
    if not os.path.exists(profiles_path):
        raise FileNotFoundError(f"Language profiles file not found: {profiles_path}")

    with open(profiles_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(
            "Language profiles JSON must be an object at top level, "
            f"got {type(data)}"
        )

    profiles: Dict[str, Dict[str, Any]] = {}
    for code, prof in data.items():
        if not isinstance(code, str):
            continue
        if not isinstance(prof, dict):
            continue
        profiles[code] = prof

    return profiles


# ---------------------------------------------------------------------------
# NLGRouter
# ---------------------------------------------------------------------------


class NLGRouter:
    """
    Router for language-specific NLG at the construction level.

    Usage:

        router = NLGRouter()
        text = router.render(
            construction_id="possession_existential",
            slots={
                "possessor": {...},
                "possessed": {...},
                "tense": "past",
            },
            lang_code="ja",
        )

    This will:
        - Load the "ja" language profile.
        - Resolve its morphology family (japonic, romance, etc.).
        - Instantiate the corresponding morphology module with that profile.
        - Import the possession_existential construction function.
        - Call it as: fn(slots, lang_profile, morph_api).
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
        """Return the language profile dict for a given language code."""
        if not isinstance(lang_code, str):
            raise TypeError("lang_code must be a string")

        try:
            return self._profiles[lang_code]
        except KeyError:
            raise KeyError(f"No language profile found for code: {lang_code!r}")

    # --------------------- morphology ---------------------------

    def _resolve_morphology_family(self, profile: Dict[str, Any]) -> str:
        """
        Decide which morphology family to use for a profile.

        Order of precedence:
            1) profile["morphology_family_override"]
            2) profile["morphology_family"]   (canonical)
            3) profile["family"]              (legacy / fallback)
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

        raise ValueError(
            "Could not determine morphology family for profile: "
            f"{profile.get('language_code', '<unknown>')}"
        )

    def _build_morphology(self, lang_code: str) -> Any:
        """
        Instantiate the morphology object for the given language.

        Uses the language profile to pick the morphology family.
        """
        profile = self.get_language_profile(lang_code)
        family = self._resolve_morphology_family(profile)

        module_path, class_name = MORPHOLOGY_CLASS_REGISTRY[family]

        module = importlib.import_module(module_path)
        try:
            morph_cls = getattr(module, class_name)
        except AttributeError:
            raise ImportError(
                f"Module {module_path!r} does not define morphology class {class_name!r}"
            )

        # Typically, we pass the entire profile as config to morphology.
        return morph_cls(profile)

    def get_morphology(self, lang_code: str) -> Any:
        """
        Return a cached morphology API instance for the language.

        Creates and caches it on first use.
        """
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

        module = importlib.import_module(module_path)
        try:
            fn = getattr(module, func_name)
        except AttributeError:
            raise ImportError(
                f"Module {module_path!r} does not define function {func_name!r}"
            )

        if not callable(fn):
            raise TypeError(f"{module_path}.{func_name} is not callable")

        self._construction_cache[key] = fn
        return fn

    def get_construction_callable(
        self,
        construction_id: str,
    ) -> Callable[..., str]:
        """
        Resolve a construction ID to a callable.

        The callable must have the signature:

            fn(slots: Any, lang_profile: dict, morph_api: Any) -> str
        """
        if construction_id not in CONSTRUCTION_REGISTRY:
            raise KeyError(f"Unknown construction_id: {construction_id!r}")

        module_path, func_name = CONSTRUCTION_REGISTRY[construction_id]
        return self._load_construction_callable(module_path, func_name)

    # --------------------- public API ---------------------------

    def render(
        self,
        construction_id: str,
        slots: Any,
        lang_code: str,
    ) -> str:
        """
        Render a sentence for the given construction, slots and language.

        Args:
            construction_id:
                ID of the construction (as in CONSTRUCTION_REGISTRY).
            slots:
                Abstract slots payload passed to the construction function.
                For most constructions this is a dict, but some may accept
                other structures (e.g. a list of clauses).
            lang_code:
                Language code (must exist in language_profiles/profiles.json).

        Returns:
            A surface string in the target language.
        """
        lang_profile = self.get_language_profile(lang_code)
        morph_api = self.get_morphology(lang_code)

        construction_fn = self.get_construction_callable(construction_id)
        return construction_fn(slots, lang_profile, morph_api)


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
    """Convenience helper to fetch a language profile via the global router."""
    return get_router().get_language_profile(lang_code)


def get_morphology(lang_code: str) -> Any:
    """
    Convenience helper to fetch the morphology API for a language
    via the global router.
    """
    return get_router().get_morphology(lang_code)


def render(
    construction_id: str,
    slots: Any,
    lang_code: str,
) -> str:
    """
    Convenience wrapper around the global router.

    Example (Wikifunctions-style usage):

        from router import render

        text = render(
            "possession_existential",
            slots={"possessor": ..., "possessed": ...},
            lang_code="ja",
        )
    """
    router = get_router()
    return router.render(construction_id, slots, lang_code)


# ---------------------------------------------------------------------------
# High-Level Biography Helper (Bridge to Engines)
# ---------------------------------------------------------------------------

# Simple cache for per-language cards to avoid re-reading JSON on every call.
_LANG_CARD_CACHE: Dict[tuple[str, str], Dict[str, Any]] = {}


def _load_language_card(family: str, lang_code: str) -> Dict[str, Any]:
    """
    Load the language card from data/<family>/<lang_code>.json,
    with a small in-memory cache.
    """
    key = (family, lang_code)
    if key in _LANG_CARD_CACHE:
        return _LANG_CARD_CACHE[key]

    # In this repository, router.py lives at the project root:
    #   C:\MyCode\AbstractWiki\abstract-wiki-architect\router.py
    # and data/ is a sibling of router.py.
    project_root = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(project_root, "data", family, f"{lang_code}.json")

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Language card not found for {lang_code} at {config_path}. "
            f"Please ensure '{family}' folder exists in 'data/' "
            f"and contains '{lang_code}.json'."
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if not isinstance(config, dict):
        raise ValueError(
            f"Language card {config_path} must be a JSON object, " f"got {type(config)}"
        )

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
    High-level helper to render a biography sentence by dispatching to
    the appropriate language family engine.

    This bridges the gap between the router and the family-specific
    logic engines in `engines/`.
    """
    router = get_router()
    profile = router.get_language_profile(lang_code)

    # Determine family (e.g. "romance", "germanic")
    family: Optional[str] = profile.get("morphology_family") or profile.get("family")
    if not family:
        raise ValueError(f"No morphology family defined for language '{lang_code}'")

    # 1. Load the Language Card (Config)
    lang_config = _load_language_card(family, lang_code)

    # 2. Import the Engine Module
    # By default we map directly from family to engines.<family>,
    # but this can later be made overridable via the profile if needed.
    engine_module_name = f"engines.{family}"
    try:
        engine_module = importlib.import_module(engine_module_name)
    except ImportError as e:
        raise ImportError(
            f"Could not import engine '{engine_module_name}' for family '{family}'"
        ) from e

    # 3. Call the engine's render_bio
    if not hasattr(engine_module, "render_bio"):
        raise NotImplementedError(
            f"Engine '{engine_module_name}' does not implement render_bio()"
        )

    return engine_module.render_bio(
        name,
        gender,
        profession_lemma,
        nationality_lemma,
        lang_config,
    )


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