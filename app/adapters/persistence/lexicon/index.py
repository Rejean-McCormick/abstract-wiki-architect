# app/adapters/persistence/lexicon/index.py
# lexicon/index.py
"""
lexicon/index.py

Enterprise-grade in-memory index over lexicon data.

This index supports two input shapes (for backwards compatibility with tests
and for the current loader reality):

1) A full Lexicon object (used by unit tests and some in-memory builders)
2) A flattened mapping produced by the loader:
      Dict[surface_form, Dict[str, Any]]
   where each value is a feature bundle (pos, gender, qid, number, etc.).

Public expectations across the codebase:
- lookup_profession(lemma_or_key) -> BaseLexicalEntry|None
- lookup_nationality(lemma_or_key) -> NationalityEntry|None
- lookup_any(lemma_or_key) -> BaseLexicalEntry|None
- lookup_by_lemma(lemma, pos=None) -> Lexeme|None
- lookup_by_qid(qid) -> Lexeme|None
- lookup_form(lemma, features, pos=None) -> Form|None

Design goals
------------
- Deterministic behavior; stable "first writer wins" semantics.
- Case-insensitive lookups, with optional robust normalization
  (underscores/spaces/dashes/punctuation) without mutating stored data.
- Minimal surface area used by engines/routers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from .types import (
    BaseLexicalEntry,
    Form,
    Lexeme,
    Lexicon,
    NationalityEntry,
)

try:
    from .normalization import normalize_for_lookup  # type: ignore
except Exception:  # pragma: no cover
    normalize_for_lookup = None  # type: ignore[assignment]


def _casefold(s: str) -> str:
    return s.casefold()


def _norm_key(s: str) -> str:
    if not isinstance(s, str):
        return ""
    if normalize_for_lookup is None:
        return s.strip().casefold()
    try:
        n = normalize_for_lookup(s)  # type: ignore[misc]
        return (n or s).strip().casefold()
    except Exception:
        return s.strip().casefold()


@dataclass
class LexiconIndex:
    """
    Index over either:
      - a Lexicon object, OR
      - a flattened mapping: surface_form -> features dict

    Notes:
      - When initialized with a Lexicon, this index preserves the original entry
        objects (ProfessionEntry, NationalityEntry, etc.) for lookup_* methods.
      - Independently, we also build a "flat" view to support lookup_by_lemma,
        lookup_by_qid, and lookup_form consistently.
    """

    lexemes: Any  # Lexicon | Dict[str, Dict[str, Any]]

    def __post_init__(self) -> None:
        # Keep a reference to the rich Lexicon if provided.
        self._lexicon: Optional[Lexicon] = self.lexemes if isinstance(self.lexemes, Lexicon) else None

        # Build the flat mapping used by lemma/qid/form APIs.
        if isinstance(self.lexemes, dict):
            self._flat: Dict[str, Dict[str, Any]] = self.lexemes
        elif isinstance(self.lexemes, Lexicon):
            self._flat = self._flatten_lexicon(self.lexemes)
        else:
            raise TypeError("LexiconIndex expects a Lexicon or a dict mapping surface_form -> feature dict.")

        # (lemma_norm, pos_norm or None) -> Lexeme
        self._lemma_index: Dict[Tuple[str, Optional[str]], Lexeme] = {}
        # lemma_norm -> Lexeme (first writer wins) to support pos=None queries
        self._lemma_anypos_index: Dict[str, Lexeme] = {}
        # qid_norm -> Lexeme
        self._qid_index: Dict[str, Lexeme] = {}
        # Normalized key -> original surface key (first writer wins)
        self._surface_canon: Dict[str, str] = {}

        # Extra indexes expected by tests / public wrapper
        self._profession_index: Dict[str, BaseLexicalEntry] = {}
        self._nationality_index: Dict[str, NationalityEntry] = {}
        self._any_index: Dict[str, BaseLexicalEntry] = {}

        # Build indices
        self._build_flat_indices()
        if self._lexicon is not None:
            self._build_rich_indices(self._lexicon)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _flatten_lexicon(self, lex: Lexicon) -> Dict[str, Dict[str, Any]]:
        """
        Convert a rich Lexicon object into the flattened mapping expected by
        the lemma/qid/form APIs.

        First writer wins on duplicate lemma keys.
        """
        flat: Dict[str, Dict[str, Any]] = {}

        for table in (
            lex.professions,
            lex.nationalities,
            lex.titles,
            lex.honours,
            lex.general_entries,
        ):
            for entry in table.values():
                surface = entry.lemma or entry.key
                if not isinstance(surface, str) or not surface.strip():
                    continue
                if surface in flat:
                    continue
                flat[surface] = entry.to_dict()

        return flat

    def _build_flat_indices(self) -> None:
        """
        Build lemma/qid indices from the flattened mapping.
        """
        for surface, feats in self._flat.items():
            if not isinstance(surface, str) or not surface.strip():
                continue
            if not isinstance(feats, Mapping):
                continue

            surface_raw = surface
            surface_norm = _norm_key(surface_raw)

            # keep first-writer-wins canonicalization
            if surface_norm and surface_norm not in self._surface_canon:
                self._surface_canon[surface_norm] = surface_raw

            pos_raw = feats.get("pos")
            pos_norm = _casefold(pos_raw) if isinstance(pos_raw, str) and pos_raw.strip() else None

            lex = Lexeme(
                key=str(feats.get("key") or surface_raw),
                lemma=surface_raw,
                pos=str(pos_raw) if isinstance(pos_raw, str) else (str(pos_raw) if pos_raw is not None else "UNKNOWN"),
                language=str(feats.get("lang") or feats.get("language") or feats.get("language_code") or ""),
                sense=str(feats.get("sense") or ""),
                human=feats.get("human") if isinstance(feats.get("human"), bool) else None,
                gender=str(feats.get("gender")) if feats.get("gender") is not None else None,
                default_number=str(feats.get("default_number")) if feats.get("default_number") is not None else feats.get("number"),
                default_formality=str(feats.get("default_formality")) if feats.get("default_formality") is not None else feats.get("formality"),
                wikidata_qid=str(feats.get("qid") or feats.get("wikidata_qid")) if (feats.get("qid") or feats.get("wikidata_qid")) else None,
                forms=dict(feats.get("forms")) if isinstance(feats.get("forms"), Mapping) else {},
                extra=dict(feats),
            )

            key_any = (surface_norm, None)
            key_pos = (surface_norm, pos_norm)

            if surface_norm and surface_norm not in self._lemma_anypos_index:
                self._lemma_anypos_index[surface_norm] = lex

            if surface_norm:
                if pos_norm is not None:
                    if key_pos not in self._lemma_index:
                        self._lemma_index[key_pos] = lex
                else:
                    if key_any not in self._lemma_index:
                        self._lemma_index[key_any] = lex

            qid = lex.wikidata_qid
            if isinstance(qid, str) and qid.strip():
                qid_norm = _norm_key(qid)
                if qid_norm and qid_norm not in self._qid_index:
                    self._qid_index[qid_norm] = lex

    def _add_alias(self, idx: Dict[str, Any], key: Optional[str], value: Any) -> None:
        if not isinstance(key, str) or not key.strip():
            return
        k = _norm_key(key)
        if k and k not in idx:
            idx[k] = value

    def _build_rich_indices(self, lex: Lexicon) -> None:
        """
        Build lookup_profession/lookup_nationality/lookup_any indices from the rich Lexicon.
        These indices preserve the original entry objects (important for NationalityEntry fields).
        """
        # professions
        for entry in lex.professions.values():
            self._add_alias(self._profession_index, entry.lemma, entry)
            self._add_alias(self._profession_index, entry.key, entry)

            self._add_alias(self._any_index, entry.lemma, entry)
            self._add_alias(self._any_index, entry.key, entry)

        # nationalities
        for entry in lex.nationalities.values():
            self._add_alias(self._nationality_index, entry.lemma, entry)
            self._add_alias(self._nationality_index, entry.key, entry)
            self._add_alias(self._nationality_index, entry.adjective, entry)
            self._add_alias(self._nationality_index, entry.demonym, entry)

            self._add_alias(self._any_index, entry.lemma, entry)
            self._add_alias(self._any_index, entry.key, entry)
            self._add_alias(self._any_index, entry.adjective, entry)
            self._add_alias(self._any_index, entry.demonym, entry)

        # titles / honours / general entries should be discoverable via lookup_any
        for table in (lex.titles, lex.honours, lex.general_entries):
            for entry in table.values():
                self._add_alias(self._any_index, entry.lemma, entry)
                self._add_alias(self._any_index, entry.key, entry)

    # ------------------------------------------------------------------
    # Public API expected by tests / lexicon.__init__
    # ------------------------------------------------------------------

    def lookup_profession(self, lemma_or_key: str) -> Optional[BaseLexicalEntry]:
        if not isinstance(lemma_or_key, str) or not lemma_or_key.strip():
            return None

        k = _norm_key(lemma_or_key)
        if self._profession_index:
            return self._profession_index.get(k)

        # Fallback: if initialized only with flat mapping, try lemma lookup
        hit = self.lookup_by_lemma(lemma_or_key, pos=None)
        return hit

    def lookup_nationality(self, lemma_or_key: str) -> Optional[NationalityEntry]:
        if not isinstance(lemma_or_key, str) or not lemma_or_key.strip():
            return None

        k = _norm_key(lemma_or_key)
        if self._nationality_index:
            return self._nationality_index.get(k)

        return None

    def lookup_any(self, lemma_or_key: str) -> Optional[BaseLexicalEntry]:
        if not isinstance(lemma_or_key, str) or not lemma_or_key.strip():
            return None

        k = _norm_key(lemma_or_key)
        if self._any_index:
            return self._any_index.get(k)

        # Fallback: flat mapping only
        return self.lookup_by_lemma(lemma_or_key, pos=None)

    # ------------------------------------------------------------------
    # Flat mapping API (used by engines/routers)
    # ------------------------------------------------------------------

    def lookup_by_lemma(self, lemma: str, *, pos: Optional[str] = None) -> Optional[Lexeme]:
        if not isinstance(lemma, str) or not lemma.strip():
            return None

        lemma_norm = _norm_key(lemma)
        if not lemma_norm:
            return None

        if pos is not None and isinstance(pos, str) and pos.strip():
            pos_norm = _casefold(pos)
            hit = self._lemma_index.get((lemma_norm, pos_norm))
            if hit is not None:
                return hit

        hit = self._lemma_anypos_index.get(lemma_norm)
        if hit is not None:
            return hit

        return self._lemma_index.get((lemma_norm, None))

    def lookup_by_qid(self, qid: str) -> Optional[Lexeme]:
        if not isinstance(qid, str) or not qid.strip():
            return None
        qid_norm = _norm_key(qid)
        if not qid_norm:
            return None
        return self._qid_index.get(qid_norm)

    def lookup_form(
        self,
        *,
        lemma: str,
        features: Optional[Dict[str, Any]] = None,
        pos: Optional[str] = None,
    ) -> Optional[Form]:
        """
        Best-effort form lookup from a lemma + features.
        """
        if not isinstance(lemma, str) or not lemma.strip():
            return None

        features = features or {}
        lex = self.lookup_by_lemma(lemma, pos=pos) or self.lookup_by_lemma(lemma, pos=None)
        if lex is None:
            return None

        req_gender = features.get("gender")
        req_number = features.get("number")

        gender = str(req_gender) if req_gender is not None else None
        number = str(req_number) if req_number is not None else None

        # 2) direct forms map (if present)
        if lex.forms:
            if gender and number:
                k = f"{gender}.{number}"
                if k in lex.forms and isinstance(lex.forms[k], str):
                    return Form(surface=lex.forms[k], features={"gender": gender, "number": number})
            if number and number in lex.forms and isinstance(lex.forms[number], str):
                return Form(surface=lex.forms[number], features={"number": number})
            if gender and gender in lex.forms and isinstance(lex.forms[gender], str):
                return Form(surface=lex.forms[gender], features={"gender": gender})

        # 3) search flattened mapping for matching surface with same qid (if known)
        qid = lex.wikidata_qid
        pos_norm = _casefold(pos) if isinstance(pos, str) and pos.strip() else None

        best_surface: Optional[str] = None

        for surface, feats in self._flat.items():
            if not isinstance(surface, str) or not isinstance(feats, Mapping):
                continue

            cand_qid = feats.get("qid") or feats.get("wikidata_qid")
            if qid and isinstance(cand_qid, str) and cand_qid.strip():
                if _norm_key(cand_qid) != _norm_key(qid):
                    continue
            elif qid:
                continue

            if pos_norm is not None:
                cand_pos = feats.get("pos")
                cand_pos_norm = _casefold(cand_pos) if isinstance(cand_pos, str) and cand_pos.strip() else None
                if cand_pos_norm != pos_norm:
                    continue

            if gender is not None:
                cand_gender = feats.get("gender")
                if cand_gender is None or str(cand_gender) != gender:
                    continue
            if number is not None:
                cand_number = feats.get("number") or feats.get("default_number")
                if cand_number is None or str(cand_number) != number:
                    continue

            best_surface = surface
            break

        if best_surface:
            out_features: Dict[str, Any] = {}
            if gender is not None:
                out_features["gender"] = gender
            if number is not None:
                out_features["number"] = number
            return Form(surface=best_surface, features=out_features)

        return Form(
            surface=lex.lemma,
            features={k: v for k, v in (("gender", gender), ("number", number)) if v is not None},
        )


__all__ = ["LexiconIndex"]
