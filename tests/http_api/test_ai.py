# tests/http_api/test_ai.py

from fastapi.testclient import TestClient

from architect_http_api.main import app

client = TestClient(app)


def test_ai_suggestions_basic() -> None:
    """
    Smoke test for the AI suggestions endpoint.

    Ensures:
    - Endpoint is reachable.
    - Response is 200 OK.
    - Payload has the expected top-level shape.
    """
    payload = {
        "utterance": "Write a short biography of Marie Curie.",
        "lang": "en",
    }

    response = client.post("/ai/suggestions", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, dict)
    assert "suggestions" in data

    suggestions = data["suggestions"]
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    first = suggestions[0]
    # Minimal contract for one suggestion item
    assert isinstance(first, dict)
    assert "frame_type" in first
    assert "title" in first
    assert "description" in first
    # confidence is optional but recommended
    if "confidence" in first:
        assert isinstance(first["confidence"], (int, float))


def test_ai_suggestions_requires_utterance() -> None:
    """
    The endpoint should validate input and reject requests without `utterance`.
    """
    payload = {
        "lang": "en"
    }

    response = client.post("/ai/suggestions", json=payload)
    # FastAPI / Pydantic validation error
    assert response.status_code == 422


def test_ai_suggestions_defaults_lang() -> None:
    """
    Lang should be optional; omitting it should still return a valid response.
    """
    payload = {
        "utterance": "Generate something about a historical figure."
    }

    response = client.post("/ai/suggestions", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)
