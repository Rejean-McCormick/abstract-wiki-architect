"""
router.py

Compatibility router for the high-level NLG frontend (nlg/api.py).

The current codebase contains multiple generation paths:
- `app/adapters/engines/engines/*`: data-driven renderers (require per-language configs)
- `app/adapters/engines/gf_engine.py` / `gf_wrapper.py`: GF-based engines (require a compiled PGF)

The frontend `nlg/api.py` expects a lightweight `router` module with at least
`render_bio(...)`. This file provides that API with safe fallbacks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol

import re


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def render_bio(
    *,
    name: str,
    gender: str = "",
    profession_lemma: str = "",
    nationality_lemma: str = "",
    lang_code: str = "en",
) -> str:
    """
    Render a single biography sentence.

    Primary goal: be safe and always return a string, even when optional
    resources (profiles/configs/PGF) are unavailable.

    Notes:
    - `gender` is currently only used for a few language templates.
    - `profession_lemma` and `nationality_lemma` are treated as surface strings.
    """
    name = _clean_text(name)
    if not name:
        return ""

    lang = _normalize_lang_code(lang_code)

    prof = _clean_text(profession_lemma)
    nat = _clean_text(nationality_lemma)

    # Try the "data-driven engine modules" path if configs exist (optional).
    text = _try_render_via_engine_modules(
        lang=lang,
        name=name,
        gender=gender,
        prof=prof,
        nat=nat,
    )
    if text:
        return _ensure_period(_clean_spaces(text))

    # Safe template fallback (no external configs required).
    text = _render_bio_fallback_template(lang=lang, name=name, gender=gender, prof=prof, nat=nat)
    return _ensure_period(_clean_spaces(text))


def get_engine(lang_code: str) -> "Engine":
    """
    Optional engine factory for `nlg/api.py`.

    This is intentionally minimal. It returns an object with a `.generate(frame, **kwargs)`
    method that produces the dict shape expected by `nlg/api.Engine`.
    """
    return _RouterEngine(lang_code=lang_code)


# -----------------------------------------------------------------------------
# Engine protocol + implementation
# -----------------------------------------------------------------------------

class Engine(Protocol):
    def generate(self, frame: Any, **kwargs: Any) -> Dict[str, Any]:
        ...


@dataclass
class _RouterEngine:
    lang_code: str

    def generate(self, frame: Any, **kwargs: Any) -> Dict[str, Any]:
        # BioFrame duck-typing (supports both nlg.semantics and app.core.domain.semantics)
        frame_type = getattr(frame, "frame_type", None)
        if frame_type == "bio" or frame.__class__.__name__ in {"BioFrame"}:
            main = getattr(frame, "main_entity", None)

            name = getattr(main, "name", "") if main is not None else getattr(frame, "name", "")
            gender = getattr(main, "gender", "") if main is not None else getattr(frame, "gender", "")

            # Prefer lemma arrays used by nlg/api's adapter.
            prof_list = (
                getattr(frame, "primary_profession_lemmas", None)
                or getattr(frame, "profession_lemmas", None)
                or []
            )
            nat_list = (
                getattr(frame, "nationality_lemmas", None)
                or getattr(frame, "nationality_lemma", None)
                or []
            )

            prof = prof_list[0] if isinstance(prof_list, list) and prof_list else (prof_list or "")
            nat = nat_list[0] if isinstance(nat_list, list) and nat_list else (nat_list or "")

            text = render_bio(
                name=str(name or ""),
                gender=str(gender or ""),
                profession_lemma=str(prof or ""),
                nationality_lemma=str(nat or ""),
                lang_code=self.lang_code,
            )
            return {"text": text, "sentences": [text] if text else []}

        # EventFrame or unknown: return empty for now (frontend handles gracefully).
        return {"text": "", "sentences": []}


# -----------------------------------------------------------------------------
# Optional integration: data-driven engine modules (requires per-language config)
# -----------------------------------------------------------------------------

def _try_render_via_engine_modules(
    *,
    lang: str,
    name: str,
    gender: str,
    prof: str,
    nat: str,
) -> str:
    """
    Best-effort call into `app/adapters/engines/engines/<family>.py` if a config is available.

    If config files are missing (common in minimal checkouts / code dumps),
    this returns "" and the caller should fall back to templates.
    """
    try:
        import json
        from pathlib import Path
        from importlib import import_module
    except Exception:
        return ""

    root = Path(__file__).resolve().parent
    profiles_path = root / "app" / "core" / "config" / "profiles" / "profiles.json"
    if not profiles_path.exists():
        return ""

    try:
        profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    prof_entry = profiles.get(lang)
    if not isinstance(prof_entry, dict):
        return ""

    family = prof_entry.get("family")
    config_rel = prof_entry.get("config")
    if not isinstance(family, str) or not family:
        return ""
    if not isinstance(config_rel, str) or not config_rel:
        return ""

    # Config path is stored as a relative path in many older versions.
    config_path = (root / config_rel).resolve()
    if not config_path.exists():
        # Often missing in trimmed dumps.
        return ""

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    try:
        mod = import_module(f"app.adapters.engines.engines.{family}")
    except Exception:
        return ""

    render_fn = getattr(mod, "render_bio", None)
    if not callable(render_fn):
        return ""

    try:
        return str(
            render_fn(
                name=name,
                gender=gender,
                prof_lemma=prof,
                nat_lemma=nat,
                config=config,
            )
        )
    except Exception:
        return ""


# -----------------------------------------------------------------------------
# Template fallback (no external resources)
# -----------------------------------------------------------------------------

def _render_bio_fallback_template(*, lang: str, name: str, gender: str, prof: str, nat: str) -> str:
    # English-like default
    if lang in {"en", "eng"}:
        if prof and nat:
            phrase = f"{nat} {prof}"
            art = _en_indefinite_article(phrase)
            return f"{name} is {art} {phrase}"
        if prof:
            art = _en_indefinite_article(prof)
            return f"{name} is {art} {prof}"
        if nat:
            return f"{name} is {nat}"
        return f"{name} is a person"

    # French (very simple, no agreement)
    if lang in {"fr", "fra"}:
        if prof and nat:
            art = "une" if _is_feminine(gender) else "un"
            return f"{name} est {art} {prof} {nat}"
        if prof:
            art = "une" if _is_feminine(gender) else "un"
            return f"{name} est {art} {prof}"
        if nat:
            return f"{name} est {nat}"
        return f"{name} est une personne"

    # Spanish (simple)
    if lang in {"es", "spa"}:
        if prof and nat:
            art = "una" if _is_feminine(gender) else "un"
            return f"{name} es {art} {prof} {nat}"
        if prof:
            art = "una" if _is_feminine(gender) else "un"
            return f"{name} es {art} {prof}"
        if nat:
            return f"{name} es {nat}"
        return f"{name} es una persona"

    # Fallback (language-agnostic)
    if prof and nat:
        return f"{name} is a {nat} {prof}"
    if prof:
        return f"{name} is a {prof}"
    if nat:
        return f"{name} is {nat}"
    return f"{name} is a person"


# -----------------------------------------------------------------------------
# Small text utilities
# -----------------------------------------------------------------------------

_VOWELS = set("aeiou")

def _normalize_lang_code(lang_code: str) -> str:
    s = (lang_code or "").strip().lower()
    if not s:
        return "en"
    s = s.replace("_", "-")
    if "-" in s:
        s = s.split("-", 1)[0]
    return s

def _clean_text(s: Any) -> str:
    if s is None:
        return ""
    t = str(s).strip()
    if len(t) >= 2 and t[0] == "[" and t[-1] == "]":
        t = t[1:-1].strip()
    t = t.replace("_", " ")
    return t

def _clean_spaces(s: str) -> str:
    return " ".join(str(s).split())

def _ensure_period(s: str) -> str:
    s = s.strip()
    if not s:
        return s
    if s.endswith((".", "!", "?")):
        return s
    return s + "."

def _en_indefinite_article(phrase: str) -> str:
    p = _clean_spaces(phrase).lower()
    if not p:
        return "a"
    m = re.search(r"[a-z0-9]", p)
    if not m:
        return "a"
    ch = m.group(0)
    return "an" if ch in _VOWELS else "a"

def _is_feminine(gender: str) -> bool:
    g = (gender or "").strip().lower()
    return g in {"f", "female", "fem", "feminine", "woman", "girl"}