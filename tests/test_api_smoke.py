# tests/test_api_smoke.py
from fastapi.testclient import TestClient
from app.adapters.api.main import create_app

app = create_app()
client = TestClient(app)

API_PREFIX = "/api/v1"


def _is_route_missing(resp) -> bool:
    """
    Distinguish FastAPI's default 404 (route not mounted) from app-level 404s.
    """
    if resp.status_code != 404:
        return False
    try:
        data = resp.json()
    except Exception:
        return True
    return isinstance(data, dict) and data.get("detail") == "Not Found"


def test_health_check_ready_exists():
    resp = client.get(f"{API_PREFIX}/health/ready")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert isinstance(data, dict)


def test_health_check_live_exists():
    resp = client.get(f"{API_PREFIX}/health/live")
    assert not _is_route_missing(resp), "The /health/live endpoint is missing!"
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)
        assert data.get("status") in ("ok", "ready", "degraded", None)


def test_generate_endpoint_structure_exists():
    """
    Accepts 422 (validation), 401/403 (auth), or 200 (success),
    but must not be missing (default 404).
    Checks both new and legacy variants.
    """
    # New style: /generate/{lang_code}
    resp = client.post(f"{API_PREFIX}/generate/eng", json={})
    if _is_route_missing(resp):
        # Legacy style: /generate
        resp = client.post(f"{API_PREFIX}/generate", json={})

    assert not _is_route_missing(resp), "No generate endpoint is mounted!"
    assert resp.status_code != 500, "Generate endpoint is mounted but crashing."


def test_list_languages_exists():
    resp = client.get(f"{API_PREFIX}/languages")
    if _is_route_missing(resp):
        resp = client.get(f"{API_PREFIX}/languages/")

    assert not _is_route_missing(resp), "The /languages endpoint is missing!"
    assert resp.status_code in (200, 401, 403), f"Unexpected status: {resp.status_code}"

    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, list) or (isinstance(data, dict) and "languages" in data)


def test_tools_run_exists_and_is_not_default_404():
    resp = client.post(f"{API_PREFIX}/tools/run", json={"tool_id": "fake_tool", "args": {}})
    assert not _is_route_missing(resp), "The /tools/run endpoint is missing!"
    assert resp.status_code in (200, 400, 401, 403, 404, 422)

    # If it's a 404, it should be an app-level 404 with a meaningful detail.
    if resp.status_code == 404:
        data = resp.json()
        assert isinstance(data, dict)
        assert data.get("detail") and data.get("detail") != "Not Found"
