# tests/http_api/test_generations.py
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapters.api.dependencies import get_generate_text_use_case, verify_api_key
from app.adapters.api.main import create_app
from app.core.domain.models import Sentence

API_PREFIX = "/api/v1"


class FakeGenerateTextUseCase:
    """
    Lightweight fake for HTTP API tests.

    It records every call so tests can assert language normalization and
    payload mapping behavior without depending on the real planner / renderer
    stack.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def execute(self, lang_code: str, frame: Any) -> Sentence:
        self.calls.append((lang_code, frame))
        subject_name = self._extract_subject_name(frame)

        text = f"Fake generated text for {subject_name} in {lang_code}"

        return Sentence(
            text=text,
            lang_code=lang_code,
            construction_id="copula_equative_simple",
            renderer_backend="safe_mode",
            fallback_used=False,
            tokens=text.split(),
            generation_time_ms=1.25,
            debug_info={
                "source": "FakeGenerateTextUseCase",
                "planner_mode": "stubbed",
            },
        )

    @staticmethod
    def _extract_subject_name(frame: Any) -> str:
        # Common case: BioFrame / compatibility Frame with .subject
        subject = getattr(frame, "subject", None)
        if isinstance(subject, dict):
            value = subject.get("name") or subject.get("label")
            if isinstance(value, str) and value.strip():
                return value.strip()

        if subject is not None:
            value = getattr(subject, "name", None) or getattr(subject, "label", None)
            if isinstance(value, str) and value.strip():
                return value.strip()

        # Fallbacks for other frame/object shapes
        for attr in ("name", "label"):
            value = getattr(frame, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()

        if isinstance(frame, dict):
            value = frame.get("name") or frame.get("label")
            if isinstance(value, str) and value.strip():
                return value.strip()

        return "Unknown"


@pytest.fixture()
def fake_use_case() -> FakeGenerateTextUseCase:
    return FakeGenerateTextUseCase()


@pytest.fixture()
def client(fake_use_case: FakeGenerateTextUseCase) -> TestClient:
    """
    Create a TestClient with generation/auth dependencies overridden.

    Overriding verify_api_key keeps the test independent from environment
    configuration while still exercising the mounted router.
    """
    app = create_app()
    app.dependency_overrides[get_generate_text_use_case] = lambda: fake_use_case
    app.dependency_overrides[verify_api_key] = lambda: "test-api-key"

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def _valid_bio_payload() -> dict[str, Any]:
    return {
        "frame_type": "bio",
        "subject": {
            "name": "Ada Lovelace",
            "gender": "f",
            "qid": "Q7259",
        },
        "properties": {
            "profession": "mathematician",
            "nationality": "British",
        },
        "meta": {
            "register": "neutral",
        },
    }


def test_generate_from_payload_success_top_level_lang(
    client: TestClient,
    fake_use_case: FakeGenerateTextUseCase,
) -> None:
    """
    POST /generate should accept language in the payload, normalize aliases,
    and preserve promoted runtime metadata in debug_info.
    """
    payload = {
        "lang": "eng",
        **_valid_bio_payload(),
    }

    response = client.post(f"{API_PREFIX}/generate", json=payload)

    assert response.status_code == 200, response.text
    data = response.json()

    assert fake_use_case.calls, "Expected fake use case to be invoked."
    assert fake_use_case.calls[-1][0] == "en"

    assert data["lang_code"] == "en"
    assert "Ada Lovelace" in data["text"]

    debug = data["debug_info"]
    assert debug["source"] == "FakeGenerateTextUseCase"
    assert debug["lang_code"] == "en"
    assert debug["construction_id"] == "copula_equative_simple"
    assert debug["renderer_backend"] == "safe_mode"
    assert debug["fallback_used"] is False
    assert debug["planner_mode"] == "stubbed"


def test_generate_from_payload_accepts_language_inside_inputs(
    client: TestClient,
    fake_use_case: FakeGenerateTextUseCase,
) -> None:
    """
    POST /generate should also accept language nested under inputs.language.
    """
    payload = {
        **_valid_bio_payload(),
        "inputs": {
            "language": "eng",
        },
    }

    response = client.post(f"{API_PREFIX}/generate", json=payload)

    assert response.status_code == 200, response.text
    data = response.json()

    assert fake_use_case.calls[-1][0] == "en"
    assert data["lang_code"] == "en"
    assert "Ada Lovelace" in data["text"]


def test_generate_from_payload_requires_language(client: TestClient) -> None:
    """
    POST /generate should reject payloads that do not specify language either
    top-level or inside inputs.
    """
    payload = _valid_bio_payload()

    response = client.post(f"{API_PREFIX}/generate", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Missing language" in detail


def test_generate_path_route_rejects_language_mismatch(client: TestClient) -> None:
    """
    When both URL and payload specify language, the URL is authoritative and
    mismatches must raise 422.
    """
    payload = {
        "lang": "fr",
        **_valid_bio_payload(),
    }

    response = client.post(f"{API_PREFIX}/generate/en", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Language mismatch" in detail


def test_generate_path_route_supports_ninai_protocol(
    client: TestClient,
    fake_use_case: FakeGenerateTextUseCase,
) -> None:
    """
    POST /generate/{lang_code} should accept Ninai payloads and forward the
    normalized language to the use case.
    """
    ninai_payload = {
        "function": "ninai.constructors.Statement",
        "args": [
            {"type": "ninai.types.Bio"},
            {
                "function": "ninai.constructors.Entity",
                "args": ["Q7259", "Ada Lovelace"],
            },
            "mathematician",
            "british",
        ],
    }

    response = client.post(f"{API_PREFIX}/generate/en", json=ninai_payload)

    assert response.status_code == 200, response.text
    data = response.json()

    assert fake_use_case.calls[-1][0] == "en"
    assert data["lang_code"] == "en"
    assert "text" in data
    assert data["debug_info"]["source"] == "FakeGenerateTextUseCase"


def test_generate_path_route_invalid_payload_returns_422(client: TestClient) -> None:
    """
    Missing frame_type / missing Ninai function should be treated as a bad
    generation request.
    """
    invalid_payload = {"broken": "data"}

    response = client.post(f"{API_PREFIX}/generate/en", json=invalid_payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "frame_type" in detail.lower() or "invalid" in detail.lower()