# tests/http_api/test_generations.py

from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from architect_http_api.main import app
from architect_http_api.services import generations_service as generations_service_module

API_PREFIX = "/abstract_wiki_architect/api"


class FakeGenerationsService:
    """
    Minimal in-memory stand-in for GenerationsService.

    It is intentionally tolerant about how the router calls it:
    - service.create_generation(request_model)
    - service.create_generation(**request_dict)
    - service.create_generation(request_dict)
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._counter: int = 0

    def _extract_payload(self, request: Any = None, **kwargs: Any) -> Dict[str, Any]:
        if request is not None:
            if isinstance(request, dict):
                data = request
            elif hasattr(request, "dict"):
                data = request.dict()  # Pydantic model
            else:
                # Fallback: generic object with attributes
                data = {
                    "frame_slug": getattr(request, "frame_slug"),
                    "language": getattr(request, "language", getattr(request, "lang", None)),
                    "fields": getattr(request, "fields"),
                    "options": getattr(request, "options", None),
                }
        else:
            data = kwargs

        frame_slug = data["frame_slug"]
        language = data.get("language") or data.get("lang")
        fields = data["fields"]
        options = data.get("options") or {}

        return {
            "frame_slug": frame_slug,
            "language": language,
            "fields": fields,
            "options": options,
        }

    async def create_generation(self, request: Any = None, **kwargs: Any) -> Dict[str, Any]:
        payload = self._extract_payload(request, **kwargs)

        self._counter += 1
        generation_id = f"gen-{self._counter}"

        record: Dict[str, Any] = {
            "id": generation_id,
            "frame_slug": payload["frame_slug"],
            "language": payload["language"],
            "fields": payload["fields"],
            "options": payload["options"],
            "text": f"Fake output for {payload['frame_slug']} in {payload['language']}",
            "debug_info": {"source": "FakeGenerationsService"},
        }

        self._store[generation_id] = record
        return record

    async def get_generation(self, generation_id: str) -> Dict[str, Any]:
        return self._store[generation_id]

    async def list_generations(
        self,
        frame_slug: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = list(self._store.values())

        if frame_slug:
            items = [g for g in items if g["frame_slug"] == frame_slug]
        if language:
            items = [g for g in items if g["language"] == language]

        total = len(items)
        sliced = items[offset : offset + limit]

        return {"items": sliced, "total": total}


@pytest.fixture()
def fake_generations_service() -> FakeGenerationsService:
    return FakeGenerationsService()


@pytest.fixture(autouse=True)
def override_generations_service(fake_generations_service: FakeGenerationsService):
    """
    Override the DI hook used by the generate router:

        Depends(generations_service.get_generations_service)
    """
    app.dependency_overrides[
        generations_service_module.get_generations_service
    ] = lambda: fake_generations_service

    try:
        yield
    finally:
        app.dependency_overrides.pop(
            generations_service_module.get_generations_service, None
        )


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _base_payload(frame_slug: str = "bio") -> Dict[str, Any]:
    return {
        "frame_slug": frame_slug,
        "language": "en",
        "fields": {
            "person_name": "Ada Lovelace",
            "gender": "female",
            "profession": "mathematician",
            "nationality": "British",
        },
        "options": {
            "register": "neutral",
            "max_sentences": 2,
        },
    }


def test_create_generation_returns_expected_shape(client: TestClient) -> None:
    payload = _base_payload()

    response = client.post(f"{API_PREFIX}/generate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["frame_slug"] == payload["frame_slug"]
    assert data["language"] == payload["language"]
    assert data["fields"]["person_name"] == "Ada Lovelace"

    assert "id" in data
    assert isinstance(data["id"], str)
    assert "text" in data and data["text"]
    assert "debug_info" in data


def test_get_generation_round_trip(client: TestClient) -> None:
    payload = _base_payload()

    create_resp = client.post(f"{API_PREFIX}/generate", json=payload)
    assert create_resp.status_code == 200
    created = create_resp.json()
    gen_id = created["id"]

    get_resp = client.get(f"{API_PREFIX}/generations/{gen_id}")
    assert get_resp.status_code == 200

    fetched = get_resp.json()
    assert fetched["id"] == gen_id
    assert fetched["frame_slug"] == payload["frame_slug"]
    assert fetched["language"] == payload["language"]
    assert fetched["text"] == created["text"]


def test_list_generations_can_filter_by_frame_slug(client: TestClient) -> None:
    bio_payload = _base_payload(frame_slug="bio")
    office_payload = _base_payload(frame_slug="office_holder")

    r1 = client.post(f"{API_PREFIX}/generate", json=bio_payload)
    r2 = client.post(f"{API_PREFIX}/generate", json=office_payload)
    assert r1.status_code == 200
    assert r2.status_code == 200

    # All generations
    list_all_resp = client.get(f"{API_PREFIX}/generations")
    assert list_all_resp.status_code == 200
    all_data = list_all_resp.json()
    assert all_data["total"] >= 2
    assert len(all_data["items"]) >= 2

    # Filtered by frame_slug
    list_bio_resp = client.get(f"{API_PREFIX}/generations", params={"frame_slug": "bio"})
    assert list_bio_resp.status_code == 200
    bio_data = list_bio_resp.json()

    assert bio_data["total"] >= 1
    assert all(item["frame_slug"] == "bio" for item in bio_data["items"])
