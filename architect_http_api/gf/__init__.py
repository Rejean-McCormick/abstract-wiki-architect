# architect_http_api/gf/__init__.py

# Try to import the engine, but don't crash if pgf is missing.
# This allows the Python-native engines (Romance, Germanic, etc.) to run on Windows
# without requiring the heavy C++ build tools for pgf.
try:
    from .engine import GFEngine, GFEngineError
except ImportError:
    import logging
    logging.getLogger(__name__).warning("PGF (Grammatical Framework) not installed. GF-based features will be disabled.")
    GFEngine = None
    GFEngineError = None

# Expose language mapping tools required by routers/services
# (These are pure Python and safe to import)
from .language_map import get_iso3_code, get_rgl_code, get_z_language

__all__ = [
    "GFEngine",
    "GFEngineError",
    "get_iso3_code",
    "get_rgl_code",
    "get_z_language",
]