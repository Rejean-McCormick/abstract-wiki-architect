from __future__ import annotations

from dataclasses import dataclass, field

import pytest

import app.adapters.persistence.lexicon.lexical_resolution as lexical_resolution
from app.adapters.persistence.lexicon.lexical_resolution import LexicalResolver
from app.core.domain.constructions.slot_models import LexemeRef


@dataclass(slots=True)
class FakeEntry:
    key: str
    lemma: str
    pos: str | None = None
    wikidata_qid: str | None = None
    forms: dict[str, str] = field(default_factory=dict)
    extra: dict[str, object] = field(default_factory=dict)


class FakeIndex:
    def __init__(
        self,
        *,
        lemma_hits: dict[tuple[str, str | None], FakeEntry] | None = None,
        qid_hits: dict[str, FakeEntry] | None = None,
        any_hits: dict[str, FakeEntry] | None = None,
    ) -> None:
        self._lemma_hits = lemma_hits or {}
        self._qid_hits = qid_hits or {}
        self._any_hits = any_hits or {}

    @staticmethod
    def _norm(text: str | None) -> str:
        return (text or "").strip().casefold()

    def lookup_by_qid(self, qid: str) -> FakeEntry | None:
        return self._qid_hits.get(self._norm(qid))

    def lookup_any(self, key: str) -> FakeEntry | None:
        return self._any_hits.get(self._norm(key))

    def lookup_by_lemma(self, lemma: str, pos: str | None = None) -> FakeEntry | None:
        norm_lemma = self._norm(lemma)
        candidates = [(norm_lemma, pos), (norm_lemma, None)]
        for candidate in candidates:
            if candidate in self._lemma_hits:
                return self._lemma_hits[candidate]
        return None


def _entry(
    *,
    lemma: str,
    pos: str | None,
    qid: str | None = None,
    lexeme_id: str | None = None,
    key: str | None = None,
    forms: dict[str, str] | None = None,
) -> FakeEntry:
    return FakeEntry(
        key=key or lemma,
        lemma=lemma,
        pos=pos,
        wikidata_qid=qid,
        forms=forms or {},
        extra={"lexeme_id": lexeme_id} if lexeme_id else {},
    )


def _install_index(monkeypatch: pytest.MonkeyPatch, index: FakeIndex) -> None:
    monkeypatch.setattr(lexical_resolution, "get_index", lambda _lang: index)


pytestmark = pytest.mark.asyncio


async def test_resolve_slot_preserves_existing_lexeme_ref() -> None:
    resolver = LexicalResolver()

    existing = LexemeRef(
        lemma="physicist",
        lexeme_id="L123",
        qid="Q169470",
        pos="NOUN",
        surface_hint="physicist",
        source="fixture",
        confidence=0.97,
        features={"number": "sg"},
    )

    result = await resolver.resolve_slot(
        lang_code="en",
        construction_id="copula_equative_classification",
        slot_name="profession",
        slot_value=existing,
    )

    assert result.kind == "lexeme_ref"
    assert result.source == "fixture"
    assert result.fallback_used is False
    assert result.unresolved is False
    assert result.resolved_value == existing
    assert result.surface_hint == "physicist"
    assert result.metadata["lexeme_id"] == "L123"
    assert result.metadata["qid"] == "Q169470"
    assert result.metadata["pos"] == "NOUN"


async def test_resolve_slot_uses_stable_qid_lookup_for_lexeme_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = FakeIndex(
        qid_hits={
            "q169470": _entry(
                lemma="physicist",
                pos="NOUN",
                qid="Q169470",
                lexeme_id="L123",
            )
        }
    )
    _install_index(monkeypatch, index)

    resolver = LexicalResolver()
    result = await resolver.resolve_slot(
        lang_code="en",
        construction_id="copula_equative_classification",
        slot_name="profession",
        slot_value="Q169470",
    )

    assert result.kind == "lexeme_ref"
    assert result.source == "stable_id"
    assert result.confidence == 1.0
    assert result.fallback_used is False
    assert result.unresolved is False

    ref = result.resolved_value
    assert isinstance(ref, LexemeRef)
    assert ref.lemma == "physicist"
    assert ref.qid == "Q169470"
    assert ref.lexeme_id == "L123"
    assert ref.pos == "NOUN"


async def test_resolve_slot_uses_alias_match_and_records_alias_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    astronaut = _entry(
        lemma="astronaut",
        pos="NOUN",
        qid="Q11631",
        lexeme_id="L900",
    )
    index = FakeIndex(
        lemma_hits={
            ("spaceman", "NOUN"): astronaut,
        }
    )
    _install_index(monkeypatch, index)

    resolver = LexicalResolver()
    result = await resolver.resolve_slot(
        lang_code="en",
        construction_id="copula_equative_classification",
        slot_name="profession",
        slot_value="spaceman",
    )

    assert result.kind == "lexeme_ref"
    assert result.source == "lexicon_alias"
    assert result.confidence == 0.75
    assert result.fallback_used is False
    assert result.unresolved is False

    ref = result.resolved_value
    assert isinstance(ref, LexemeRef)
    assert ref.lemma == "astronaut"
    assert ref.qid == "Q11631"
    assert ref.lexeme_id == "L900"
    assert result.metadata["alias_used"] == "spaceman"


async def test_resolve_slot_raw_string_fallback_keeps_slot_pos_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_index(monkeypatch, FakeIndex())

    resolver = LexicalResolver()
    result = await resolver.resolve_slot(
        lang_code="en",
        construction_id="copula_equative_classification",
        slot_name="profession",
        slot_value="chrononaut",
    )

    assert result.kind == "lexeme_ref"
    assert result.source == "raw_string"
    assert result.confidence == 0.25
    assert result.fallback_used is True
    assert result.unresolved is False

    ref = result.resolved_value
    assert isinstance(ref, LexemeRef)
    assert ref.lemma == "chrononaut"
    assert ref.pos == "NOUN"
    assert ref.surface_hint == "chrononaut"


async def test_resolve_slot_none_returns_unresolved_result() -> None:
    resolver = LexicalResolver()

    result = await resolver.resolve_slot(
        lang_code="en",
        construction_id="copula_equative_classification",
        slot_name="profession",
        slot_value=None,
    )

    assert result.kind == "unresolved"
    assert result.source == "missing"
    assert result.confidence == 0.0
    assert result.fallback_used is False
    assert result.unresolved is True
    assert result.resolved_value is None


async def test_resolve_slot_map_materializes_resolved_values_and_populates_lexical_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    physicist = _entry(
        lemma="physicist",
        pos="NOUN",
        qid="Q169470",
        lexeme_id="L123",
    )
    french = _entry(
        lemma="French",
        pos="ADJ",
        qid="Q150",
        lexeme_id="L456",
    )

    index = FakeIndex(
        lemma_hits={
            ("physicist", "NOUN"): physicist,
            ("french", "ADJ"): french,
        }
    )
    _install_index(monkeypatch, index)

    resolver = LexicalResolver()
    slot_map = {
        "profession": "physicist",
        "nationality": "French",
        "year": 1903,
    }

    resolved = await resolver.resolve_slot_map(
        slot_map,
        lang_code="en",
        construction_id="copula_equative_classification",
    )

    assert list(resolved.keys()) == [
        "profession",
        "nationality",
        "year",
        "lexical_bindings",
    ]
    assert isinstance(resolved["profession"], LexemeRef)
    assert isinstance(resolved["nationality"], LexemeRef)
    assert resolved["year"] == 1903

    bindings = resolved["lexical_bindings"]
    assert list(bindings.keys()) == ["profession", "nationality", "year"]

    assert bindings["profession"]["kind"] == "lexeme_ref"
    assert bindings["profession"]["source"] == "language_lexicon"
    assert bindings["profession"]["lemma"] == "physicist"
    assert bindings["profession"]["qid"] == "Q169470"
    assert bindings["profession"]["fallback_used"] is False

    assert bindings["nationality"]["kind"] == "lexeme_ref"
    assert bindings["nationality"]["pos"] == "ADJ"
    assert bindings["nationality"]["lemma"] == "French"

    assert bindings["year"]["kind"] == "literal"
    assert bindings["year"]["source"] == "literal_passthrough"
    assert bindings["year"]["fallback_used"] is False


async def test_resolve_slot_map_is_deterministic_and_does_not_mutate_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    physicist = _entry(
        lemma="physicist",
        pos="NOUN",
        qid="Q169470",
        lexeme_id="L123",
    )
    index = FakeIndex(
        lemma_hits={
            ("physicist", "NOUN"): physicist,
        }
    )
    _install_index(monkeypatch, index)

    resolver = LexicalResolver()
    slot_map = {
        "profession": "physicist",
        "year": 1903,
    }
    original = dict(slot_map)

    first = await resolver.resolve_slot_map(
        slot_map,
        lang_code="en",
        construction_id="copula_equative_classification",
    )
    second = await resolver.resolve_slot_map(
        slot_map,
        lang_code="en",
        construction_id="copula_equative_classification",
    )

    assert slot_map == original
    assert "lexical_bindings" not in slot_map
    assert first == second


async def test_resolve_plan_returns_updated_mapping_with_top_level_lexical_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    physicist = _entry(
        lemma="physicist",
        pos="NOUN",
        qid="Q169470",
        lexeme_id="L123",
    )
    index = FakeIndex(
        lemma_hits={
            ("physicist", "NOUN"): physicist,
        }
    )
    _install_index(monkeypatch, index)

    resolver = LexicalResolver()
    plan = {
        "construction_id": "copula_equative_classification",
        "lang_code": "en",
        "generation_options": {"debug": True},
        "slot_map": {
            "profession": "physicist",
            "year": 1903,
        },
    }

    resolved_plan = await resolver.resolve_plan(construction_plan=plan)

    assert resolved_plan is not plan
    assert resolved_plan["construction_id"] == "copula_equative_classification"
    assert isinstance(resolved_plan["slot_map"]["profession"], LexemeRef)
    assert resolved_plan["slot_map"]["year"] == 1903

    assert resolved_plan["lexical_bindings"] == resolved_plan["slot_map"]["lexical_bindings"]
    assert resolved_plan["lexical_bindings"]["profession"]["lemma"] == "physicist"
    assert resolved_plan["lexical_bindings"]["profession"]["fallback_used"] is False

    assert plan["slot_map"]["profession"] == "physicist"
    assert "lexical_bindings" not in plan


async def test_resolve_sequence_aggregates_item_metadata_and_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    physicist = _entry(
        lemma="physicist",
        pos="NOUN",
        qid="Q169470",
        lexeme_id="L123",
    )
    index = FakeIndex(
        lemma_hits={
            ("physicist", "NOUN"): physicist,
        }
    )
    _install_index(monkeypatch, index)

    resolver = LexicalResolver()
    result = await resolver.resolve_slot(
        lang_code="en",
        construction_id="copula_equative_classification",
        slot_name="profession",
        slot_value=["physicist", "chrononaut"],
    )

    assert result.kind == "lexeme_ref_list"
    assert result.source == "sequence"
    assert result.fallback_used is True
    assert result.unresolved is False
    assert result.confidence == 0.25

    resolved_values = result.resolved_value
    assert len(resolved_values) == 2
    assert isinstance(resolved_values[0], LexemeRef)
    assert isinstance(resolved_values[1], LexemeRef)
    assert resolved_values[0].lemma == "physicist"
    assert resolved_values[1].lemma == "chrononaut"
    assert resolved_values[1].source == "raw_string"

    items = result.metadata["items"]
    assert len(items) == 2
    assert items[0]["fallback_used"] is False
    assert items[1]["fallback_used"] is True