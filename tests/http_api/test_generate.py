# tests/http_api/test_generate.py

from dataclasses import dataclass

from fastapi.testclient import TestClient

from architect_http_api import main as app_module
from nlg.api import GenerationResult as CoreGenerationResult
from architect_http_api.services import nlg_client as nlg_client_module


# ---------------------------------------------------------------------------
# App + dependency wiring
# ---------------------------------------------------------------------------

# Support both patterns:
# - main.app
# - main.create_app()
if hasattr(app_module, "create_app"):
    app = app_module.create_app()
else:
    app = app_module.app

client = TestClient(app)


@dataclass
class DummyFrame:
    frame_type: str
    payload: dict


class DummyNLGClient:
    def generate(self, req):
        # Generic dummy implementation that does not depend on real frames
        frame = DummyFrame(frame_type=req.frame_type, payload=req.frame)

        return CoreGenerationResult(
            text="Marie Curie was a Polish-French physicist.",
            sentences=["Marie Curie was a Polish-French physicist."],
            lang=req.lang,
            frame=frame,
            debug_info={"source": "dummy-test"},
        )


def override_nlg_client():
    return DummyNLGClient()


# Override the real NLG client with our dummy for all tests in this module
app.dependency_overrides[nlg_client_module.get_nlg_client] = override_nlg_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_generate_success_minimal_payload():
    """
    Happy-path test: minimal valid payload returns a 200 with expected shape.
    """
    payload = {
        "lang": "en",
        "frame_type": "entity.person",
        "frame": {
            "person": {"qid": "Q7186", "label": "Marie Curie"},
        },
        # options/debug are optional and omitted here
    }

    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["text"] == "Marie Curie was a Polish-French physicist."
    assert data["lang"] == "en"
    assert data["frame_type"] == "entity.person"

    # Basic structure checks
    assert isinstance(data.get("sentences"), list)
    assert data["sentences"] == ["Marie Curie was a Polish-French physicist."]

    # Frame echo / debug structure is implementation-dependent but should exist
    assert "frame" in data
    assert "debug_info" in data
    assert data["debug_info"].get("source") == "dummy-test"


def test_generate_validation_error_missing_lang():
    """
    If required fields are missing, FastAPI/Pydantic should return 422.
    """
    payload = {
        # "lang" is intentionally omitted
        "frame_type": "entity.person",
        "frame": {"person": {"qid": "Q42"}},
    }

    response = client.post("/api/generate", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["detail"]  # FastAPI validation error details are present


def test_generate_validation_error_missing_frame_type():
    """
    Missing frame_type should also yield 422.
    """
    payload = {
        "lang": "en",
        # "frame_type" omitted
        "frame": {"person": {"qid": "Q42"}},
    }

    response = client.post("/api/generate", json=payload)
    assert response.status_code == 422
