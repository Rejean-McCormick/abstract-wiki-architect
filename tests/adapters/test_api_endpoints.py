# tests\adapters\test_api_endpoints.py
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from app.adapters.api.main import create_app
from app.shared.config import settings
from app.core.domain.models import Sentence

@pytest.fixture
def client(container):
    """
    Returns a FastAPI TestClient.
    
    The 'container' fixture (from conftest.py) has already overridden 
    the Core dependencies (Broker, Engine, Repo) with Mocks.
    """
    app = create_app()
    with TestClient(app) as c:
        yield c

class TestGenerationEndpoint:
    
    def test_generate_success(self, client, mock_grammar_engine):
        """
        Scenario: Valid request with correct API Key.
        Expected: 200 OK and the generated text.
        """
        # Arrange
        mock_grammar_engine.generate.return_value = Sentence(
            text="Success text", 
            lang_code="eng"
        )
        
        payload = {
            "frame_type": "bio",
            "subject": {"name": "Test"},
            "properties": {}
        }
        headers = {"x-api-key": settings.API_KEY}

        # Act
        response = client.post("/generate/eng", json=payload, headers=headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["text"] == "Success text"
        assert data["lang_code"] == "eng"

    def test_generate_unauthorized(self, client):
        """
        Scenario: Missing or invalid API Key.
        Expected: 403 Forbidden.
        """
        payload = {"frame_type": "bio", "subject": {}}
        
        # Missing header
        response = client.post("/generate/eng", json=payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Invalid header
        headers = {"x-api-key": "wrong_key"}
        response = client.post("/generate/eng", json=payload, headers=headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_generate_validation_error(self, client):
        """
        Scenario: Invalid JSON payload (missing required fields).
        Expected: 422 Unprocessable Entity.
        """
        headers = {"x-api-key": settings.API_KEY}
        # Payload missing 'frame_type' and 'subject'
        response = client.post("/generate/eng", json={"bad": "data"}, headers=headers)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

class TestManagementEndpoints:

    def test_onboard_language_success(self, client, mock_broker):
        """
        Scenario: Valid onboarding request.
        Expected: 201 Created and Side Effect (Event Published).
        """
        payload = {
            "code": "zul",
            "name": "Zulu",
            "family": "Bantu"
        }
        headers = {"x-api-key": settings.API_KEY}

        response = client.post("/languages/", json=payload, headers=headers)

        assert response.status_code == status.HTTP_201_CREATED
        assert "successfully onboarded" in response.json()["message"]
        
        # Verify the background build was triggered
        assert mock_broker.publish.called

    def test_trigger_build_accepted(self, client, mock_broker):
        """
        Scenario: Manual build trigger.
        Expected: 202 Accepted.
        """
        payload = {"strategy": "fast"}
        headers = {"x-api-key": settings.API_KEY}

        response = client.post("/languages/eng/build", json=payload, headers=headers)

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "event_id" in response.json()

class TestHealthEndpoints:
    
    def test_liveness(self, client):
        response = client.get("/health/live")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "ok"

    def test_readiness_healthy(self, client):
        """
        Scenario: All mocks return True for health check.
        Expected: 200 OK.
        """
        response = client.get("/health/ready")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["broker"] == "up"
        assert data["engine"] == "up"

    def test_readiness_unhealthy(self, client, mock_broker):
        """
        Scenario: Broker is down.
        Expected: 503 Service Unavailable.
        """
        # Simulate Broker failure
        mock_broker.health_check.return_value = False
        
        response = client.get("/health/ready")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["broker"] == "down"