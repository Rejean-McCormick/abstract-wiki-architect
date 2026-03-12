# app/shared/lexicon.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import structlog

try:
    from app.shared.config import settings
except ImportError:  # pragma: no cover - compatibility bootstrap
    settings = None

logger = structlog.get_logger()

_QID_RE = re.compile(r"^Q\d+$", re.IGNORECASE)


@dataclass(slots=True)
class LexiconEntry:
    """
    Backwards-compatible lightweight lexical entry.

    This remains the public return type of `app.shared.lexicon` so legacy code
    can keep calling:

        lexicon.lookup(...)
        lexicon.get_entry(...)
        lexicon.get_facts(...)

    The canonical runtime lexical-resolution boundary lives elsewhere
    (`app.adapters.persistence.lexicon.*`), and this module now acts as a
    compatibility facade over that adapter surface.
    """

    lemma: str
    pos: str
    gf_fun: str
    qid: Optional[str]
    source: str
    features: Dict[str, Any]


class LexiconRuntime:
    """
    Compatibility facade over the authoritative lexicon adapter package.

    Preferred behavior:
    - normalize language codes consistently,
    - delegate lookups to `app.adapters.persistence.lexicon`,
    - convert rich adapter entries into stable legacy `LexiconEntry` objects.

    Fallback behavior:
    - if the adapter package is unavailable or incomplete during migration,
      fall back to the older shard-based JSON loading path.

    Notes
    -----
    This class is intentionally retained because current callers still import
    `LexiconRuntime` / `lexicon` directly. New lexical-resolution logic should
    live behind the shared lexical-resolution contract rather than here.
    """

    _instance: "LexiconRuntime | None" = None

    # Legacy fallback storage
    _legacy_data: Dict[str, Dict[str, LexiconEntry]] = {}
    _legacy_loaded_langs: set[str] = set()

    # Shared normalization map
    _iso_map: Dict[str, str] = {}

    def __new__(cls) -> "LexiconRuntime":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_iso_config()
        return cls._instance

    # ------------------------------------------------------------------ #
    # Paths / config
    # ------------------------------------------------------------------ #

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def _candidate_repo_roots(self) -> List[Path]:
        roots: List[Path] = []

        if settings and hasattr(settings, "FILESYSTEM_REPO_PATH"):
            try:
                roots.append(Path(settings.FILESYSTEM_REPO_PATH))
            except Exception:
                pass

        roots.append(self._project_root())
        roots.append(Path.cwd())
        return roots

    def _candidate_iso_config_paths(self) -> List[Path]:
        candidates: List[Path] = []
        for root in self._candidate_repo_roots():
            candidates.extend(
                [
                    root / "data" / "config" / "iso_to_wiki.json",
                    root / "config" / "iso_to_wiki.json",
                ]
            )
        return candidates

    def _load_iso_config(self) -> None:
        """
        Load `iso_to_wiki.json` and build a canonical code -> ISO-639-1 map.
        """
        try:
            candidates = self._candidate_iso_config_paths()
            config_path = next((p for p in candidates if p.exists()), None)

            if not config_path:
                logger.warning(
                    "lexicon_config_missing",
                    searched_paths=[str(c) for c in candidates],
                )
                self._use_fallback_map()
                return

            with config_path.open("r", encoding="utf-8") as f:
                raw_map = json.load(f)

            rgl_groups: Dict[str, List[str]] = {}
            for code, rgl_suffix in raw_map.items():
                if isinstance(rgl_suffix, Mapping):
                    rgl_suffix = rgl_suffix.get("wiki")

                if not isinstance(code, str) or not rgl_suffix:
                    continue

                rgl_groups.setdefault(str(rgl_suffix), []).append(code)

            iso_map: Dict[str, str] = {}
            for rgl_suffix, codes in rgl_groups.items():
                canonical = next((c for c in codes if len(c) == 2), codes[0])

                iso_map[rgl_suffix.lower()] = canonical
                for code in codes:
                    iso_map[code.lower()] = canonical

            self._iso_map = iso_map
            logger.info(
                "lexicon_config_loaded",
                source=str(config_path),
                mappings=len(self._iso_map),
            )

        except Exception as exc:  # pragma: no cover - safety path
            logger.error("lexicon_init_error", error=str(exc))
            self._use_fallback_map()

    def _use_fallback_map(self) -> None:
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

    # ------------------------------------------------------------------ #
    # Public normalization API
    # ------------------------------------------------------------------ #

    def normalize_code(self, code: str) -> str:
        """
        Normalize ISO-2 / ISO-3 / RGL-style inputs to canonical ISO-639-1.
        """
        value = (code or "").strip().lower()
        if value.startswith("wiki"):
            value = value[4:]

        if len(value) == 2:
            return value

        return self._iso_map.get(value, value[:2])

    # ------------------------------------------------------------------ #
    # Adapter-first lookup path
    # ------------------------------------------------------------------ #

    def _get_adapter_index(self, lang_code: str) -> Any:
        try:
            from app.adapters.persistence.lexicon import get_index

            return get_index(self.normalize_code(lang_code))
        except Exception as exc:
            logger.debug("lexicon_adapter_index_unavailable", error=str(exc))
            return None

    def _adapter_available_languages(self) -> List[str]:
        try:
            from app.adapters.persistence.lexicon import available_languages

            langs = available_languages()
            if isinstance(langs, Iterable):
                return [self.normalize_code(str(lang)) for lang in langs if str(lang).strip()]
        except Exception as exc:
            logger.debug("lexicon_adapter_languages_unavailable", error=str(exc))
        return []

    def _adapter_lookup_qid(self, lang_code: str, qid: str) -> Any:
        try:
            from app.adapters.persistence.lexicon import lookup_qid

            return lookup_qid(self.normalize_code(lang_code), qid)
        except Exception as exc:
            logger.debug("lexicon_adapter_qid_lookup_failed", qid=qid, error=str(exc))
            return None

    def _adapter_lookup_lemma(
        self,
        lang_code: str,
        lemma: str,
        *,
        pos: Optional[str] = None,
    ) -> Any:
        try:
            from app.adapters.persistence.lexicon import lookup_lemma

            return lookup_lemma(self.normalize_code(lang_code), lemma, pos=pos)
        except Exception as exc:
            logger.debug(
                "lexicon_adapter_lemma_lookup_failed",
                lemma=lemma,
                pos=pos,
                error=str(exc),
            )
            return None

    @staticmethod
    def _mapping_copy(value: Any) -> Dict[str, Any]:
        return dict(value) if isinstance(value, Mapping) else {}

    def _coerce_to_legacy_entry(
        self,
        raw: Any,
        *,
        default_source: str,
    ) -> Optional[LexiconEntry]:
        """
        Convert adapter-level rich entries to the legacy `LexiconEntry` shape.
        """
        if raw is None:
            return None
        if isinstance(raw, LexiconEntry):
            return raw

        extra = self._mapping_copy(getattr(raw, "extra", None))
        raw_features = self._mapping_copy(getattr(raw, "features", None))

        lemma = (
            getattr(raw, "lemma", None)
            or getattr(raw, "label", None)
            or getattr(raw, "key", None)
            or extra.get("lemma")
            or extra.get("label")
            or ""
        )
        lemma = str(lemma).strip()
        if not lemma:
            return None

        pos = (
            getattr(raw, "pos", None)
            or extra.get("pos")
            or extra.get("part_of_speech")
            or "X"
        )

        qid = (
            getattr(raw, "wikidata_qid", None)
            or getattr(raw, "qid", None)
            or extra.get("wikidata_qid")
            or extra.get("qid")
            or None
        )
        if qid is not None:
            qid = str(qid).strip() or None

        gf_fun = (
            getattr(raw, "gf_fun", None)
            or extra.get("gf_fun")
            or extra.get("gf")
            or ""
        )

        source = (
            getattr(raw, "source", None)
            or extra.get("source")
            or default_source
        )

        features: Dict[str, Any] = {}
        features.update(raw_features)
        features.update(extra)

        for attr_name in (
            "sense",
            "human",
            "gender",
            "default_number",
            "default_formality",
            "adjective",
            "demonym",
            "country_name",
            "position",
        ):
            value = getattr(raw, attr_name, None)
            if value is not None:
                features.setdefault(attr_name, value)

        forms = getattr(raw, "forms", None)
        if isinstance(forms, Mapping) and forms:
            features.setdefault("forms", dict(forms))

        return LexiconEntry(
            lemma=lemma,
            pos=str(pos),
            gf_fun=str(gf_fun),
            qid=qid,
            source=str(source),
            features=features,
        )

    # ------------------------------------------------------------------ #
    # Legacy raw-shard fallback path
    # ------------------------------------------------------------------ #

    def _legacy_load_language(self, lang_code: str) -> None:
        iso2 = self.normalize_code(lang_code)
        if not iso2 or iso2 in self._legacy_loaded_langs:
            return

        base_path = self._candidate_repo_roots()[0]
        shard_names = [
            "wide.json",
            "core.json",
            "people.json",
            "science.json",
            "geography.json",
        ]

        self._legacy_data.setdefault(iso2, {})
        loaded_shards: List[str] = []

        for shard_name in shard_names:
            shard_path = base_path / "data" / "lexicon" / iso2 / shard_name
            if not shard_path.exists():
                continue

            try:
                with shard_path.open("r", encoding="utf-8") as f:
                    raw_data = json.load(f)

                if not isinstance(raw_data, Mapping):
                    continue

                for _, value in raw_data.items():
                    entry_data = value[0] if isinstance(value, list) and value else value
                    if not isinstance(entry_data, Mapping):
                        continue

                    features = dict(entry_data.get("features", {}) or {})
                    facts = entry_data.get("facts")
                    if isinstance(facts, Mapping):
                        features.update(dict(facts))

                    entry = LexiconEntry(
                        lemma=str(entry_data.get("lemma", "unknown")),
                        pos=str(entry_data.get("pos", "noun")),
                        gf_fun=str(entry_data.get("gf_fun", "")),
                        qid=(
                            str(entry_data.get("qid") or entry_data.get("wnid")).strip()
                            if (entry_data.get("qid") or entry_data.get("wnid"))
                            else None
                        ),
                        source=str(entry_data.get("source", shard_name)),
                        features=features,
                    )

                    if entry.qid:
                        self._legacy_data[iso2][entry.qid] = entry
                    self._legacy_data[iso2][entry.lemma.lower()] = entry

                loaded_shards.append(shard_name)

            except json.JSONDecodeError:
                logger.error(
                    "lexicon_json_corrupt",
                    lang=iso2,
                    path=str(shard_path),
                )
            except Exception as exc:
                logger.error(
                    "lexicon_load_failed",
                    lang=iso2,
                    shard=shard_name,
                    error=str(exc),
                )

        self._legacy_loaded_langs.add(iso2)

        if loaded_shards:
            logger.info(
                "lexicon_loaded_success",
                lang=iso2,
                total_entries=len(self._legacy_data[iso2]),
                shards=loaded_shards,
            )
        else:
            logger.warning("lexicon_no_shards_found", lang=iso2)

    def _legacy_lookup(self, key: str, lang_code: str) -> Optional[LexiconEntry]:
        if not key:
            return None

        iso2 = self.normalize_code(lang_code)
        self._legacy_load_language(iso2)

        lang_db = self._legacy_data.get(iso2)
        if not lang_db:
            return None

        return lang_db.get(key) or lang_db.get(key.lower())

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def adapter_available(self) -> bool:
        return self._get_adapter_index("en") is not None or bool(self._adapter_available_languages())

    def available_languages(self) -> List[str]:
        langs = self._adapter_available_languages()
        if langs:
            return sorted(set(langs))
        return sorted(self._legacy_loaded_langs)

    def load_language(self, lang_code: str) -> None:
        """
        Warm whichever backend is currently authoritative/available.

        Adapter-first:
            build the per-language index via `app.adapters.persistence.lexicon`.

        Fallback:
            load the legacy raw shards.
        """
        iso2 = self.normalize_code(lang_code)

        idx = self._get_adapter_index(iso2)
        if idx is not None:
            logger.debug("lexicon_adapter_warmed", lang=iso2)
            return

        self._legacy_load_language(iso2)

    def lookup(self, key: str, lang_code: str) -> Optional[LexiconEntry]:
        """
        Universal compatibility lookup.

        Resolution strategy:
        1. adapter QID lookup for QIDs,
        2. adapter lemma lookup,
        3. legacy raw-shard fallback.
        """
        if not key:
            return None

        iso2 = self.normalize_code(lang_code)
        raw_key = str(key).strip()
        if not raw_key:
            return None

        adapter_hit: Any = None
        if _QID_RE.match(raw_key):
            adapter_hit = self._adapter_lookup_qid(iso2, raw_key)
            if adapter_hit is not None:
                return self._coerce_to_legacy_entry(
                    adapter_hit,
                    default_source="adapter.lookup_qid",
                )

        adapter_hit = self._adapter_lookup_lemma(iso2, raw_key)
        if adapter_hit is not None:
            return self._coerce_to_legacy_entry(
                adapter_hit,
                default_source="adapter.lookup_lemma",
            )

        return self._legacy_lookup(raw_key, iso2)

    def lookup_qid(self, lang_code: str, qid: str) -> Optional[LexiconEntry]:
        if not qid:
            return None
        hit = self._adapter_lookup_qid(lang_code, qid)
        if hit is not None:
            return self._coerce_to_legacy_entry(hit, default_source="adapter.lookup_qid")
        return self._legacy_lookup(qid, lang_code)

    def lookup_lemma(
        self,
        lang_code: str,
        lemma: str,
        *,
        pos: Optional[str] = None,
    ) -> Optional[LexiconEntry]:
        if not lemma:
            return None
        hit = self._adapter_lookup_lemma(lang_code, lemma, pos=pos)
        if hit is not None:
            return self._coerce_to_legacy_entry(
                hit,
                default_source="adapter.lookup_lemma",
            )
        return self._legacy_lookup(lemma, lang_code)

    def get_entry(self, lang_code: str, qid: str) -> Optional[LexiconEntry]:
        """
        Backwards-compatible alias expected by older callers such as NinaiAdapter.
        """
        return self.lookup(qid, lang_code)

    def get_facts(self, lang_code: str, qid: str, property_id: str) -> List[str]:
        """
        Return semantic facts from the compatibility entry shape.

        This preserves the old `features[property_id]` lookup behavior.
        """
        entry = self.get_entry(lang_code, qid)
        if not entry or not entry.features:
            return []

        value = entry.features.get(property_id, [])
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        if isinstance(value, str):
            return [value]
        return []

    # ------------------------------------------------------------------ #
    # Optional migration helpers
    # ------------------------------------------------------------------ #

    def resolve_entity(
        self,
        value: object,
        *,
        lang_code: str,
        generation_options: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        """
        Best-effort pass-through to the Batch-5 entity resolver when available.
        """
        try:
            from app.adapters.persistence.lexicon.entity_resolution import resolve_entity

            return resolve_entity(
                value,
                lang_code=self.normalize_code(lang_code),
                generation_options=dict(generation_options or {}),
            )
        except Exception as exc:
            logger.debug("lexicon_entity_resolution_unavailable", error=str(exc))
            return None

    def resolve_predicate(
        self,
        value: object,
        *,
        lang_code: str,
        pos: Optional[str] = None,
        generation_options: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        """
        Best-effort pass-through to the Batch-5 predicate resolver when available.
        """
        try:
            from app.adapters.persistence.lexicon.predicate_resolution import (
                resolve_predicate,
            )

            return resolve_predicate(
                value,
                lang_code=self.normalize_code(lang_code),
                pos=pos,
                generation_options=dict(generation_options or {}),
            )
        except Exception as exc:
            logger.debug("lexicon_predicate_resolution_unavailable", error=str(exc))
            return None


lexicon = LexiconRuntime()

__all__ = [
    "LexiconEntry",
    "LexiconRuntime",
    "lexicon",
]