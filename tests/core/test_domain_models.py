# tests\core\test_domain_models.py
import pytest
from pydantic import ValidationError
from app.core.domain.models import Frame, Sentence, LexiconEntry, Language, LanguageStatus

class TestFrameModel:
    def test_valid_frame_creation(self):
        """Should successfully create a Frame with valid data."""
        data = {
            "frame_type": "bio",
            "subject": {"name": "Test Subject", "qid": "Q1"},
            "properties": {"prop": "value"}
        }
        frame = Frame(**data)
        assert frame.frame_type == "bio"
        assert frame.subject["name"] == "Test Subject"

    def test_frame_missing_required_fields(self):
        """Should raise ValidationError if required fields are missing."""
        # Missing 'frame_type'
        with pytest.raises(ValidationError):
            Frame(subject={"name": "No Type"})
        
        # Missing 'subject'
        with pytest.raises(ValidationError):
            Frame(frame_type="bio")

    def test_frame_immutability_check(self):
        """
        Frames are theoretically immutable value objects, 
        but Pydantic V2 allows mutation unless configured otherwise.
        We check basic attribute access here.
        """
        frame = Frame(frame_type="test", subject={})
        frame.frame_type = "new_type"
        assert frame.frame_type == "new_type"

class TestLexiconEntryModel:
    def test_valid_entry(self):
        entry = LexiconEntry(
            lemma="chat",
            pos="N",
            source="wikidata",
            features={"gender": "masc"}
        )
        assert entry.lemma == "chat"
        assert entry.pos == "N"

    def test_entry_default_values(self):
        """Test default values for optional fields."""
        entry = LexiconEntry(lemma="run", pos="V")
        assert entry.source == "manual"
        assert entry.features == {}

class TestLanguageModel:
    def test_language_status_defaults(self):
        lang = Language(code="eng", name="English")
        assert lang.status == LanguageStatus.PLANNED
        assert lang.code == "eng"