import json
import structlog
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

# Attempt to load settings
try:
    from app.shared.config import settings
except ImportError:
    settings = None

logger = structlog.get_logger()


@dataclass(slots=True)
class LexiconEntry:
    """
    Lightweight data container for a lexical entry.
    Slots reduce per-instance memory overhead.
    """
    lemma: str
    pos: str
    gf_fun: str
    qid: Optional[str]
    source: str
    # Semantic lookups (e.g. P106/Occupation)
    features: Dict[str, Any]


class LexiconRuntime:
    """
    Singleton In-Memory Database for Zone B (Lexicon).

    Configuration:
    - Loads 'config/iso_to_wiki.json' to build the 3-letter -> 2-letter normalization map.
    - Lazy loads language shards from 'data/lexicon/{iso2}/'.
    - Loads manual shards (core, people) over the bulk harvest (wide).
    """
    _instance = None
    _data: Dict[str, Dict[str, LexiconEntry]] = {}
    _loaded_langs = set()
    _iso_map: Dict[str, str] = {}  # e.g. 'eng' -> 'en', 'Afr' -> 'af'

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_iso_config()
        return cls._instance

    @staticmethod
    def _project_root() -> Path:
        # app/shared/lexicon.py -> project root
        return Path(__file__).resolve().parents[2]

    def _load_iso_config(self) -> None:
        """
        Loads 'config/iso_to_wiki.json' to create a unified normalization map.
        This file maps codes to RGL suffixes (e.g., "en": "Eng", "eng": "Eng").
        We reverse this to map everything to the canonical 2-letter ISO code.
        """
        try:
            candidates: List[Path] = []

            # 1) Highest priority: explicit repo path override
            if settings and hasattr(settings, "FILESYSTEM_REPO_PATH"):
                repo_root = Path(settings.FILESYSTEM_REPO_PATH)
                candidates += [
                    repo_root / "data" / "config" / "iso_to_wiki.json",
                    repo_root / "config" / "iso_to_wiki.json",
                ]

            # 2) Relative to project root derived from this file
            project_root = self._project_root()
            candidates += [
                project_root / "data" / "config" / "iso_to_wiki.json",
                project_root / "config" / "iso_to_wiki.json",
            ]

            # 3) Fallback: current working directory
            cwd = Path.cwd()
            candidates += [
                cwd / "data" / "config" / "iso_to_wiki.json",
                cwd / "config" / "iso_to_wiki.json",
            ]

            config_path = next((p for p in candidates if p.exists()), None)

            if not config_path:
                logger.warning(
                    "lexicon_config_missing",
                    searched_paths=[str(c) for c in candidates],
                )
                self._use_fallback_map()
                return

            with open(config_path, "r", encoding="utf-8") as f:
                raw_map = json.load(f)

            # Group keys by their RGL value to find canonical 2-letter code
            rgl_groups: Dict[str, List[str]] = {}
            for code, rgl_suffix in raw_map.items():
                if isinstance(rgl_suffix, dict):
                    # v2 format: { "wiki": "Eng", "name": "English" }
                    rgl_suffix = rgl_suffix.get("wiki")

                if not rgl_suffix:
                    continue

                rgl_groups.setdefault(rgl_suffix, []).append(code)

            # Build lookup map
            iso_map: Dict[str, str] = {}
            for rgl_suffix, codes in rgl_groups.items():
                canonical = next((c for c in codes if len(c) == 2), codes[0])

                # Map suffix itself (e.g. 'Eng' -> 'en')
                iso_map[rgl_suffix.lower()] = canonical

                # Map variants (e.g. 'eng' -> 'en', 'en' -> 'en')
                for c in codes:
                    iso_map[c.lower()] = canonical

            self._iso_map = iso_map
            logger.info(
                "lexicon_config_loaded",
                source=str(config_path),
                mappings=len(self._iso_map),
            )

        except Exception as e:
            logger.error("lexicon_init_error", error=str(e))
            self._use_fallback_map()

    def _use_fallback_map(self) -> None:
        """Minimal fallback for bootstrapping."""
        self._iso_map = {
            "eng": "en",
            "fra": "fr",
            "deu": "de",
            "nld": "nl",
            "ita": "it",
            "spa": "es",
            "rus": "ru",
            "swe": "sv",
            "zho": "zh",
            "jpn": "ja",
            "ara": "ar",
            "hin": "hi",
        }

    def _normalize_lang_code(self, code: str) -> str:
        """Normalizes ISO-2 / ISO-3 / RGL suffix / 'wiki' prefix to ISO-2."""
        code = (code or "").lower()
        if code.startswith("wiki"):
            code = code[4:]

        if len(code) == 2:
            return code

        return self._iso_map.get(code, code[:2])

    def load_language(self, lang_code: str) -> None:
        """
        Lazy-loads the lexicon shards for a specific language.
        Loads 'wide.json' first, then overrides with 'core', 'people', etc.
        """
        iso2 = self._normalize_lang_code(lang_code)
        if not iso2 or iso2 in self._loaded_langs:
            return

        base_path = (
            Path(settings.FILESYSTEM_REPO_PATH)
            if settings and hasattr(settings, "FILESYSTEM_REPO_PATH")
            else self._project_root()
        )

        shards_to_load = ["wide.json", "core.json", "people.json", "science.json", "geography.json"]

        self._data.setdefault(iso2, {})

        loaded_shards: List[str] = []

        for shard_name in shards_to_load:
            shard_path = base_path / "data" / "lexicon" / iso2 / shard_name
            if not shard_path.exists():
                continue

            try:
                with open(shard_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)

                for _, val in raw_data.items():
                    # Handle v1 (list) or v2 (dict) format
                    entry_data = val[0] if isinstance(val, list) and val else val
                    if not isinstance(entry_data, dict):
                        continue

                    features = dict(entry_data.get("features", {}) or {})
                    facts = entry_data.get("facts")
                    if isinstance(facts, dict):
                        features.update(facts)

                    entry_obj = LexiconEntry(
                        lemma=entry_data.get("lemma", "unknown"),
                        pos=entry_data.get("pos", "noun"),
                        gf_fun=entry_data.get("gf_fun", ""),
                        qid=entry_data.get("qid") or entry_data.get("wnid"),
                        source=entry_data.get("source", shard_name),
                        features=features,
                    )

                    # Primary index: QID
                    if entry_obj.qid:
                        self._data[iso2][entry_obj.qid] = entry_obj

                    # Secondary index: lemma
                    self._data[iso2][entry_obj.lemma.lower()] = entry_obj

                loaded_shards.append(shard_name)

            except json.JSONDecodeError:
                logger.error("lexicon_json_corrupt", lang=iso2, path=str(shard_path))
            except Exception as e:
                logger.error("lexicon_load_failed", lang=iso2, shard=shard_name, error=str(e))

        self._loaded_langs.add(iso2)

        if loaded_shards:
            logger.info(
                "lexicon_loaded_success",
                lang=iso2,
                total_entries=len(self._data[iso2]),
                shards=loaded_shards,
            )
        else:
            logger.warning("lexicon_no_shards_found", lang=iso2)

    def lookup(self, key: str, lang_code: str) -> Optional[LexiconEntry]:
        """Universal lookup: QID (Q42) or string (Apple)."""
        if not key:
            return None

        iso2 = self._normalize_lang_code(lang_code)
        self.load_language(iso2)

        lang_db = self._data.get(iso2)
        if not lang_db:
            return None

        return lang_db.get(key) or lang_db.get(key.lower())

    def get_entry(self, lang_code: str, qid: str) -> Optional[LexiconEntry]:
        """Alias for retrieving by QID (used by NinaiAdapter)."""
        return self.lookup(qid, lang_code)

    def get_facts(self, lang_code: str, qid: str, property_id: str) -> List[str]:
        """Returns semantic facts (e.g. P106) for an entity QID."""
        entry = self.get_entry(lang_code, qid)
        if not entry or not entry.features:
            return []

        v = entry.features.get(property_id, [])
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [v]
        return []


# --- EXPORT THE SINGLETON ---
lexicon = LexiconRuntime()
