# tests/http_api/test_generate.py
from typing import Any
import pytest
from fastapi.testclient import TestClient

# FIX: Import from correct v2.1 locations
from app.adapters.api.main import create_app
from app.adapters.api.dependencies import get_generate_text_use_case
from app.core.domain.models import Sentence

# FIX: V2.1 API Prefix Standard
API_PREFIX = "/api/v1"


class FakeGenerateTextUseCase:
    """
    Mock implementation of the GenerateText Use Case.
    Used to bypass the complex logic of the real Engine/LLM integration.
    """

    async def execute(self, lang_code: str, frame: Any) -> Sentence:
        # Return a fixed Sentence object matching the test expectation
        return Sentence(
            text="Marie Curie was a Polish-French physicist.",
            lang_code=lang_code,
            debug_info={"source": "dummy-test"},
        )


@pytest.fixture
def fake_use_case():
    return FakeGenerateTextUseCase()


@pytest.fixture
def client(fake_use_case):
    """
    Returns a FastAPI TestClient with the Use Case mocked.
    """
    app = create_app()

    # Override the dependency used in the router
    app.dependency_overrides[get_generate_text_use_case] = lambda: fake_use_case

    with TestClient(app) as c:
        yield c

    # Clean up overrides
    app.dependency_overrides.clear()


def test_generate_success_minimal_payload(client: TestClient):
    """
    Happy-path test: minimal valid payload returns a 200 with expected shape.
    """
    # Updated payload structure to match v2.1 BioFrame requirements
    payload = {
        "frame_type": "bio",
        "subject": {"name": "Marie Curie", "qid": "Q7186"},
        "properties": {"label": "Marie Curie"},
    }
    lang = "en"

    # [FIX] Add Auth Header (pytest default key)
    headers = {"x-api-key": "test-api-key"}

    # Updated URL pattern: /api/v1/generate/{lang_code}
    response = client.post(
        f"{API_PREFIX}/generate/{lang}",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()
    assert data["text"] == "Marie Curie was a Polish-French physicist."
    assert data["lang_code"] == "en"

    # Check debug info
    assert "debug_info" in data
    assert data["debug_info"].get("source") == "dummy-test"


def test_generate_validation_error_missing_frame_type(client: TestClient):
    """
    Missing frame_type should yield 422 (Validation Error).
    """
    payload = {
        "subject": {"name": "Marie Curie", "qid": "Q7186"}
        # Missing frame_type
    }
    lang = "en"

    # [FIX] Add Auth Header (pytest default key)
    headers = {"x-api-key": "test-api-key"}

    response = client.post(
        f"{API_PREFIX}/generate/{lang}",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 422


def test_generate_validation_error_invalid_structure(client: TestClient):
    """
    Invalid structure (e.g., missing subject for bio frame) should yield 422.
    """
    payload = {
        "frame_type": "bio",
        "properties": {}
        # Missing 'subject' field required by BioFrame
    }
    lang = "en"

    # [FIX] Add Auth Header (pytest default key)
    headers = {"x-api-key": "test-api-key"}

    response = client.post(
        f"{API_PREFIX}/generate/{lang}",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 422
