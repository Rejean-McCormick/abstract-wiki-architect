# tests\adapters\test_wikidata_adapter.py
import pytest
from unittest.mock import patch, MagicMock
from app.adapters.persistence.wikidata_adapter import WikidataAdapter
from app.shared.resilience import CircuitBreakerOpenError

# Sample SPARQL JSON Response from Wikidata
MOCK_SPARQL_RESPONSE = {
    "results": {
        "bindings": [
            {
                "lemma": {"value": "Alan Turing"},
                "langLabel": {"value": "en"}
            }
        ]
    }
}

@pytest.mark.asyncio
class TestWikidataAdapter:

    async def test_fetch_lexemes_success(self):
        """
        Scenario: Wikidata returns a valid JSON response.
        Expected: Adapter parses it into a list of LexiconEntry objects.
        """
        # Arrange
        adapter = WikidataAdapter()
        qid = "Q7251"
        lang = "en"

        # Mock the httpx.AsyncClient context manager
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__aenter__.return_value
            
            # Setup the mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = MOCK_SPARQL_RESPONSE
            mock_response.raise_for_status.return_value = None
            
            mock_client.get.return_value = mock_response

            # Act
            # We bypass the circuit breaker 'call' wrapper for direct unit testing of logic
            # or we ensure the circuit is closed.
            results = await adapter.fetch_lexemes(qid, lang)

            # Assert
            assert len(results) == 1
            assert results[0].lemma == "Alan Turing"
            assert results[0].features["qid"] == qid
            
            # Verify the URL was correct
            mock_client.get.assert_called_once()
            args, kwargs = mock_client.get.call_args
            assert "query" in kwargs["params"]

    async def test_fetch_lexemes_network_error(self):
        """
        Scenario: HTTP request fails (e.g., 500 error or timeout).
        Expected: Exception is raised (to be caught by circuit breaker in real usage).
        """
        import httpx
        adapter = WikidataAdapter()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = mock_client_cls.return_value.__aenter__.return_value
            
            # Simulate HTTP Error
            mock_client.get.side_effect = httpx.HTTPError("Network Down")

            # Act & Assert
            with pytest.raises(httpx.HTTPError):
                await adapter.fetch_lexemes("Q1", "en")

    async def test_circuit_breaker_open(self):
        """
        Scenario: The circuit breaker is explicitly open.
        Expected: Adapter returns empty list immediately without making requests.
        """
        # Arrange
        adapter = WikidataAdapter()
        # Manually trip the breaker
        adapter.circuit_breaker.state = "open"

        with patch("httpx.AsyncClient") as mock_client_cls:
            # Act
            results = await adapter.fetch_lexemes("Q1", "en")
            
            # Assert
            assert results == []
            # Verify NO network call was attempted
            mock_client_cls.assert_not_called()