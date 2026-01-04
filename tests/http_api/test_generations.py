# tests/http_api/test_generations.py
from typing import Any, Dict
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock  # kept (even though unused)

from app.adapters.api.main import create_app
from app.adapters.api.dependencies import get_generate_text_use_case
from app.core.domain.models import Sentence

# Correct v2.1 API Prefix
API_PREFIX = "/api/v1"

class FakeGenerateTextUseCase:
    """
    Mock implementation of the GenerateText Use Case.
    Bypasses the complex Grammar Engine and LLM logic for API testing.
    """
    async def execute(self, lang_code: str, frame: Any) -> Sentence:
        # Simulate successful generation logic
        subject_name = "Unknown"
        
        # [FIX] Handle both BioFrame objects and Ninai (recursive dicts)
        # 1. Pydantic Model (BioFrame)
        if hasattr(frame, "subject"):
            if isinstance(frame.subject, dict):
                subject_name = frame.subject.get("name", "Unknown")
            elif hasattr(frame.subject, "name"):
                subject_name = frame.subject.name
                
        # 2. Ninai Protocol (Recursive Dict) - Simplified Extraction
        # In a real scenario, the NinaiAdapter converts this to a Frame BEFORE
        # calling the UseCase. If the UseCase receives a raw dict, it means
        # the Router passed it directly (which shouldn't happen with correct Adapter binding),
        # or we are testing a lower-level path.
        # However, for this Mock, we just want to return a string.
        
        # If frame came from NinaiAdapter, it is ALREADY a Frame object.
        # So the logic above (hasattr frame, "subject") covers it.
        
        return Sentence(
            text=f"Fake generated text for {subject_name} in {lang_code}",
            lang_code=lang_code,
            debug_info={"source": "FakeGenerateTextUseCase"}
        )

@pytest.fixture()
def fake_use_case() -> FakeGenerateTextUseCase:
    return FakeGenerateTextUseCase()

@pytest.fixture()
def client(fake_use_case: FakeGenerateTextUseCase) -> TestClient:
    """
    Creates a TestClient with the GenerateText dependency overridden.
    """
    app = create_app()
    
    # Override the dependency in the FastAPI app
    app.dependency_overrides[get_generate_text_use_case] = lambda: fake_use_case
    
    with TestClient(app) as c:
        yield c
    
    # Cleanup overrides
    app.dependency_overrides.clear()

def _valid_bio_payload() -> Dict[str, Any]:
    """Returns a valid v2.1 BioFrame payload."""
    return {
        "frame_type": "bio",
        "subject": {
            "name": "Ada Lovelace",
            "gender": "f",
            "qid": "Q7259"
        },
        "properties": {
            "profession": "mathematician",
            "nationality": "British"
        },
        "meta": {
            "register": "neutral"
        }
    }

def test_generate_endpoint_success(client: TestClient) -> None:
    """
    Verifies that POST /generate/{lang} returns 200 OK and the expected structure.
    """
    payload = _valid_bio_payload()
    lang_code = "eng"
    
    # [FIX] Add Auth Header (pytest default key)
    headers = {"x-api-key": "test-api-key"}

    response = client.post(
        f"{API_PREFIX}/generate/{lang_code}", 
        json=payload,
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify Domain Entity (Sentence) serialization
    assert data["lang_code"] == lang_code
    assert "Ada Lovelace" in data["text"]
    assert "text" in data
    assert data["debug_info"]["source"] == "FakeGenerateTextUseCase"

def test_generate_validation_error(client: TestClient) -> None:
    """
    Verifies that sending an invalid payload raises 422.
    """
    # Missing 'frame_type' and 'subject'
    invalid_payload = {"broken": "data"}
    lang_code = "eng"
    
    # [FIX] Add Auth Header (pytest default key)
    headers = {"x-api-key": "test-api-key"}

    response = client.post(
        f"{API_PREFIX}/generate/{lang_code}", 
        json=invalid_payload,
        headers=headers
    )
    
    assert response.status_code == 422

def test_generate_ninai_protocol_detection(client: TestClient) -> None:
    """
    Verifies that the router correctly accepts Ninai Protocol payloads.
    """
    # Minimal valid Ninai payload (recursive tree)
    ninai_payload = {
        "function": "ninai.constructors.Statement",
        "args": [
            {"type": "ninai.types.Bio"},
            {"function": "ninai.constructors.Entity", "args": ["Q7259", "Ada Lovelace"]},
            "mathematician",
            "british"
        ]
    }
    
    # [FIX] Add Auth Header (pytest default key)
    headers = {"x-api-key": "test-api-key"}
    
    response = client.post(
        f"{API_PREFIX}/generate/eng", 
        json=ninai_payload,
        headers=headers
    )
    
    # Should succeed (200) if adapter works
    assert response.status_code == 200
    assert "Ada Lovelace" in response.json()["text"]
