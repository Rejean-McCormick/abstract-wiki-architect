# tests/http_api/test_entities.py

from fastapi.routing import APIRoute

from architect_http_api.main import app


def _get_api_routes() -> list[APIRoute]:
    """Return only FastAPI APIRoute objects (ignore static/docs/etc.)."""
    return [r for r in app.routes if isinstance(r, APIRoute)]


def test_entities_routes_registered_under_api_prefix() -> None:
    """
    The entities router must expose at least one route under /api/entities.
    This ensures the router is included in architect_http_api.main.
    """
    routes = _get_api_routes()
    entities_paths = {r.path for r in routes if r.path.startswith("/api/entities")}

    assert entities_paths, "Expected at least one /api/entities route to be registered."


def test_entities_routes_are_tagged_entities() -> None:
    """
    All /api/entities routes should be tagged with 'entities' so they are easy
    to discover in OpenAPI / docs and for tooling.
    """
    routes = _get_api_routes()
    entities_routes = [r for r in routes if r.path.startswith("/api/entities")]

    # If this fails, the first test will already have pointed out missing routes.
    assert entities_routes, "No /api/entities routes found to check tags."

    for route in entities_routes:
        assert (
            "entities" in route.tags
        ), f"Route {route.path} is missing the 'entities' tag."
