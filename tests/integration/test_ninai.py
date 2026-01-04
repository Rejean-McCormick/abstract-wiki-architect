# tests/integration/test_ninai.py
import pytest
from app.adapters.ninai import ninai_adapter
from app.core.domain.frame import BioFrame

# ==============================================================================
# FIXTURES: Sample Ninai Payloads
# ==============================================================================

@pytest.fixture
def valid_ninai_bio():
    """
    A standard valid Ninai Biographical Statement.
    Represents: (Statement (Bio (Entity Q123 "Alan Turing") "computer_scientist" "british"))
    """
    return {
        "function": "ninai.constructors.Statement",
        "args": [
            {"type": "ninai.types.Bio"},  # Arg 0: Type Definition
            {
                "function": "ninai.constructors.Entity",
                "args": ["Q7251", "Alan Turing"]
            },
            "computer_scientist",          # Arg 2: Profession (String)
            "british"                      # Arg 3: Nationality (String)
        ]
    }

@pytest.fixture
def valid_ninai_bio_recursive_entity():
    """
    A Bio Statement where profession/nationality are also Entity objects (not just strings).
    Represents: (Statement (Bio ... (Entity Q82955 "computer_scientist")))
    """
    return {
        "function": "ninai.constructors.Statement",
        "args": [
            {"type": "ninai.types.Bio"},
            {
                "function": "ninai.constructors.Entity",
                "args": ["Q7251", "Alan Turing"]
            },
            {
                "function": "ninai.constructors.Entity",
                "args": ["Q82955", "computer_scientist"]
            }
        ]
    }

@pytest.fixture
def invalid_ninai_root():
    """Missing root function."""
    return {"args": []}

@pytest.fixture
def malformed_bio_missing_args():
    """Bio Statement missing mandatory arguments (like Subject)."""
    # NOTE: In v2.1, Missing profession might be auto-filled by Lexicon,
    # so we remove the Subject (Arg 1) to force a crash.
    return {
        "function": "ninai.constructors.Statement",
        "args": [
            {"type": "ninai.types.Bio"}
            # Missing Subject entirely
        ]
    }

# ==============================================================================
# TESTS
# ==============================================================================

def test_parse_valid_bio_standard(valid_ninai_bio):
    """
    Test parsing a standard flat-argument BioFrame.
    """
    result = ninai_adapter.parse(valid_ninai_bio)
    
    assert isinstance(result, BioFrame)
    assert result.frame_type == "bio"
    # [FIX] Access fields via property alias OR nested subject dict
    assert result.name == "Alan Turing"
    assert result.qid == "Q7251"
    
    # [FIX] Access fields directly on the Pydantic model
    # The adapter populates these fields directly on the Entity object
    assert result.subject.profession == "computer_scientist"
    assert result.subject.nationality == "british"

def test_parse_valid_bio_recursive(valid_ninai_bio_recursive_entity):
    """
    Test parsing where arguments are nested Entity objects.
    The adapter should extract the label/ID correctly.
    """
    result = ninai_adapter.parse(valid_ninai_bio_recursive_entity)
    
    assert isinstance(result, BioFrame)
    assert result.name == "Alan Turing"
    
    # [FIX] Access fields directly on the Pydantic model
    assert result.subject.profession == "computer_scientist" 
    assert result.subject.nationality is None

def test_invalid_root_structure(invalid_ninai_root):
    """
    Test that invalid root keys raise ValueError.
    """
    with pytest.raises(ValueError) as exc:
        ninai_adapter.parse(invalid_ninai_root)
    assert "Invalid Root" in str(exc.value)

def test_malformed_bio_args(malformed_bio_missing_args):
    """
    Test that missing required arguments raise ValueError.
    """
    with pytest.raises(ValueError) as exc:
        ninai_adapter.parse(malformed_bio_missing_args)
    assert "Malformed BioFrame" in str(exc.value)

def test_unsupported_type():
    """
    Test that unknown Ninai types are rejected.
    """
    payload = {
        "function": "ninai.constructors.Statement",
        "args": [{"type": "ninai.types.UnknownSomething"}]
    }
    with pytest.raises(ValueError) as exc:
        ninai_adapter.parse(payload)
    assert "Unsupported Ninai Type" in str(exc.value)