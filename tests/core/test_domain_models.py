# tests/core/test_domain_models.py
import pytest
from pydantic import ValidationError

from app.core.domain.models import (
    BaseFrame,
    BioFrame,
    EventFrame,
    Frame,
    GenerationRequest,
    GrammarType,
    Language,
    LanguageStatus,
    LexiconEntry,
    RelationalFrame,
    Sentence,
    SurfaceResult,
)


class TestFrameModel:
    def test_valid_nested_bio_frame_creation(self):
        frame = Frame(
            frame_type="bio",
            subject={"name": "Test Subject", "qid": "Q1"},
            properties={"prop": "value"},
            meta={"source": "unit_test"},
        )

        assert frame.frame_type == "bio"
        assert frame.subject["name"] == "Test Subject"
        assert frame.subject_qid == "Q1"
        assert frame.properties["prop"] == "value"
        assert frame.meta["source"] == "unit_test"
        assert frame.normalized_frame_type == "bio"
        assert frame.is_bio_like is True
        assert frame.is_event_like is False
        assert frame.is_relation_like is False

    def test_flat_person_payload_is_normalized_into_subject_and_properties(self):
        frame = Frame(
            frame_type="entity.person",
            name=" Alan Turing ",
            profession=" mathematician ",
            nationality=" British ",
            gender=" male ",
            qid=" Q7251 ",
        )

        assert frame.normalized_frame_type == "bio"
        assert frame.subject == {
            "name": "Alan Turing",
            "profession": "mathematician",
            "nationality": "British",
            "gender": "male",
            "qid": "Q7251",
        }
        assert frame.properties["name"] == "Alan Turing"
        assert frame.properties["profession"] == "mathematician"
        assert frame.properties["nationality"] == "British"
        assert frame.properties["gender"] == "male"
        assert frame.properties["qid"] == "Q7251"
        assert frame.subject_name == "Alan Turing"
        assert frame.subject_qid == "Q7251"

    def test_main_entity_and_lemma_lists_are_promoted_into_compat_properties(self):
        frame = Frame(
            frame_type="bio",
            main_entity={"name": "Marie Curie", "qid": "Q7186"},
            primary_profession_lemmas=["physicist", "chemist"],
            nationality_lemmas=["Polish", "French"],
        )

        assert frame.subject["name"] == "Marie Curie"
        assert frame.subject["qid"] == "Q7186"
        assert frame.main_entity == {"name": "Marie Curie", "qid": "Q7186"}
        assert frame.properties["primary_profession_lemmas"] == ["physicist", "chemist"]
        assert frame.properties["profession"] == "physicist"
        assert frame.properties["nationality_lemmas"] == ["Polish", "French"]
        assert frame.properties["nationality"] == "Polish"

    def test_bio_like_frames_require_subject_or_flat_person_fields(self):
        with pytest.raises(ValidationError):
            Frame(frame_type="bio")

        with pytest.raises(ValidationError):
            Frame(frame_type="entity.person")

    def test_non_bio_frame_can_exist_without_subject(self):
        frame = Frame(frame_type="custom.unknown")

        assert frame.frame_type == "custom.unknown"
        assert frame.subject == {}
        assert frame.normalized_frame_type == "custom.unknown"

    @pytest.mark.parametrize(
        ("frame_type", "expected"),
        [
            ("bio", "bio"),
            ("entity.person", "bio"),
            ("person", "bio"),
            ("event.transitive", "event"),
            ("event", "event"),
            ("relation", "relational"),
            ("membership_affiliation", "relational"),
        ],
    )
    def test_normalized_frame_type_maps_legacy_aliases(self, frame_type, expected):
        frame = Frame(frame_type=frame_type, subject={"name": "X"} if expected == "bio" else {})
        assert frame.normalized_frame_type == expected

    def test_to_bio_frame_returns_canonical_bio_frame(self):
        frame = Frame(
            frame_type="entity.person",
            name="Ada Lovelace",
            profession="mathematician",
            nationality="British",
            qid="Q7259",
            context_id="Q7259",
            style="formal",
            meta={"origin": "legacy"},
        )

        canonical = frame.to_bio_frame()

        assert isinstance(canonical, BioFrame)
        assert canonical.frame_type == "bio"
        assert canonical.subject["name"] == "Ada Lovelace"
        assert canonical.style == "formal"
        assert canonical.context_id == "Q7259"
        assert canonical.meta["origin"] == "legacy"
        assert canonical.meta["properties"]["profession"] == "mathematician"

    def test_to_event_frame_returns_canonical_event_frame(self):
        frame = Frame(
            frame_type="event.transitive",
            subject={"name": "Marie Curie"},
            event_object="the Solvay Conference",
            event_type="participation",
            date="1911",
            location="Brussels",
            properties={"importance": "high"},
            meta={"source": "unit_test"},
        )

        canonical = frame.to_event_frame()

        assert isinstance(canonical, EventFrame)
        assert canonical.frame_type == "event"
        assert canonical.subject["name"] == "Marie Curie"
        assert canonical.event_object == "the Solvay Conference"
        assert canonical.event_type == "participation"
        assert canonical.date == "1911"
        assert canonical.location == "Brussels"
        assert canonical.meta["source"] == "unit_test"
        assert canonical.meta["properties"]["importance"] == "high"

    def test_to_relational_frame_requires_relation(self):
        frame = Frame(
            frame_type="relation",
            subject={"name": "Marie Curie"},
            object={"name": "Pierre Curie"},
        )

        with pytest.raises(ValueError, match="Relational frames require `relation`"):
            frame.to_relational_frame()

    def test_to_relational_frame_returns_canonical_relational_frame(self):
        frame = Frame(
            frame_type="membership_affiliation",
            subject={"name": "Marie Curie"},
            relation="member_of",
            object={"name": "French Academy of Medicine"},
            properties={"start_year": 1922},
            meta={"source": "unit_test"},
        )

        canonical = frame.to_relational_frame()

        assert isinstance(canonical, RelationalFrame)
        assert canonical.frame_type == "relational"
        assert canonical.subject["name"] == "Marie Curie"
        assert canonical.relation == "member_of"
        assert canonical.object == {"name": "French Academy of Medicine"}
        assert canonical.meta["source"] == "unit_test"
        assert canonical.meta["properties"]["start_year"] == 1922

    def test_to_canonical_frame_returns_base_frame_for_unknown_types(self):
        frame = Frame(
            frame_type="custom.experimental",
            subject={"name": "X"},
            properties={"foo": "bar"},
            meta={"source": "test"},
            context_id="ctx-1",
        )

        canonical = frame.to_canonical_frame()

        assert isinstance(canonical, BaseFrame)
        assert canonical.context_id == "ctx-1"
        assert canonical.meta["frame_type"] == "custom.experimental"
        assert canonical.meta["subject"] == {"name": "X"}
        assert canonical.meta["properties"] == {"foo": "bar"}
        assert canonical.meta["source"] == "test"


class TestSurfaceResultModels:
    def test_surface_result_syncs_required_debug_info_keys(self):
        result = SurfaceResult(
            text="Marie Curie is a physicist.",
            lang_code="ENG",
            construction_id="copula_equative_simple",
            renderer_backend="gf",
            fallback_used=True,
            debug_info={"custom": "value"},
            generation_time_ms=12.5,
        )

        assert result.text == "Marie Curie is a physicist."
        assert result.lang_code == "eng"
        assert result.construction_id == "copula_equative_simple"
        assert result.renderer_backend == "gf"
        assert result.fallback_used is True
        assert result.generation_time_ms == 12.5
        assert result.debug_info["custom"] == "value"
        assert result.debug_info["construction_id"] == "copula_equative_simple"
        assert result.debug_info["renderer_backend"] == "gf"
        assert result.debug_info["lang_code"] == "eng"
        assert result.debug_info["fallback_used"] is True

    def test_surface_result_preserves_existing_debug_info_values(self):
        result = SurfaceResult(
            text="Bonjour.",
            lang_code="fr",
            construction_id="copula_equative_simple",
            renderer_backend="family",
            fallback_used=False,
            debug_info={
                "construction_id": "already-set",
                "renderer_backend": "manual",
                "lang_code": "custom-fr",
                "fallback_used": True,
            },
        )

        assert result.debug_info["construction_id"] == "already-set"
        assert result.debug_info["renderer_backend"] == "manual"
        assert result.debug_info["lang_code"] == "custom-fr"
        assert result.debug_info["fallback_used"] is True

    def test_sentence_is_backwards_compatible_surface_result(self):
        sentence = Sentence(
            text="Alan Turing was a mathematician.",
            lang_code="EN",
            construction_id="copula_equative_classification",
            renderer_backend="safe_mode",
        )

        assert isinstance(sentence, SurfaceResult)
        assert sentence.text == "Alan Turing was a mathematician."
        assert sentence.lang_code == "en"
        assert sentence.debug_info["construction_id"] == "copula_equative_classification"
        assert sentence.debug_info["renderer_backend"] == "safe_mode"
        assert sentence.debug_info["lang_code"] == "en"
        assert sentence.debug_info["fallback_used"] is False

    def test_surface_result_requires_text_and_lang_code(self):
        with pytest.raises(ValidationError):
            SurfaceResult(lang_code="en")

        with pytest.raises(ValidationError):
            SurfaceResult(text="Hello", lang_code="")


class TestLexiconEntryModel:
    def test_valid_entry(self):
        entry = LexiconEntry(
            lemma="chat",
            pos="N",
            source="wikidata",
            features={"gender": "masc"},
            confidence=0.75,
        )

        assert entry.lemma == "chat"
        assert entry.pos == "N"
        assert entry.source == "wikidata"
        assert entry.features == {"gender": "masc"}
        assert entry.confidence == 0.75

    def test_entry_default_values(self):
        entry = LexiconEntry(lemma="run", pos="V")

        assert entry.source == "manual"
        assert entry.features == {}
        assert entry.confidence == 1.0

    def test_entry_rejects_blank_required_text_fields(self):
        with pytest.raises(ValidationError):
            LexiconEntry(lemma="", pos="N")

        with pytest.raises(ValidationError):
            LexiconEntry(lemma="run", pos="")

        with pytest.raises(ValidationError):
            LexiconEntry(lemma="run", pos="V", source="")

    def test_entry_none_confidence_defaults_to_one(self):
        entry = LexiconEntry(lemma="walk", pos="V", confidence=None)
        assert entry.confidence == 1.0


class TestLanguageModel:
    def test_language_defaults_and_normalization(self):
        lang = Language(code="ENG", name="English")

        assert lang.code == "eng"
        assert lang.name == "English"
        assert lang.status == LanguageStatus.PLANNED
        assert lang.grammar_type == GrammarType.FACTORY
        assert lang.build_strategy == "fast"
        assert lang.family is None
        assert lang.last_build_time is None
        assert lang.error_log is None

    def test_language_accepts_explicit_status_and_grammar_type(self):
        lang = Language(
            code="fr",
            name="French",
            status=LanguageStatus.READY,
            grammar_type=GrammarType.RGL,
            build_strategy="full",
            family="Romance",
        )

        assert lang.code == "fr"
        assert lang.status == LanguageStatus.READY
        assert lang.grammar_type == GrammarType.RGL
        assert lang.build_strategy == "full"
        assert lang.family == "Romance"

    def test_language_rejects_invalid_code(self):
        with pytest.raises(ValidationError):
            Language(code="", name="Invalid")

        with pytest.raises(ValidationError):
            Language(code="ENGLISH", name="Invalid")

        with pytest.raises(ValidationError):
            Language(code="e1", name="Invalid")


class TestGenerationRequestModel:
    def test_generation_request_accepts_semantic_frame_alias(self):
        request = GenerationRequest(
            semantic_frame={
                "frame_type": "bio",
                "subject": {"name": "Ada Lovelace", "qid": "Q7259"},
                "properties": {"profession": "mathematician"},
            },
            target_language="ENG",
        )

        assert isinstance(request.semantic_frame, Frame)
        assert request.semantic_frame.subject["name"] == "Ada Lovelace"
        assert request.target_language == "eng"
        assert request.lang_code == "eng"

    def test_generation_request_accepts_legacy_aliases(self):
        request = GenerationRequest(
            frame={
                "frame_type": "entity.person",
                "name": "Alan Turing",
                "profession": "mathematician",
                "qid": "Q7251",
            },
            lang="EN",
        )

        assert request.semantic_frame.normalized_frame_type == "bio"
        assert request.semantic_frame.subject["name"] == "Alan Turing"
        assert request.target_language == "en"
        assert request.lang_code == "en"

    def test_generation_request_requires_target_language(self):
        with pytest.raises(ValidationError):
            GenerationRequest(
                semantic_frame={
                    "frame_type": "bio",
                    "subject": {"name": "No Lang"},
                }
            )