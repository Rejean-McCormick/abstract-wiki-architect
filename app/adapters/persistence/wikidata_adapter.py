# app/adapters/persistence/wikidata_adapter.py
import httpx
import structlog
from typing import List, Optional, Dict, Any
from app.shared.config import settings
from app.shared.resilience import (
    get_circuit_breaker, 
    retry_external_api, 
    CircuitBreakerOpenError
)
from app.core.domain.models import LexiconEntry

logger = structlog.get_logger()

class WikidataAdapter:
    """
    Adapter for querying the Wikidata SPARQL endpoint.
    
    Responsibilities:
    1. Fetch labels/aliases for concepts (Fallout strategy).
    2. Fetch detailed Lexemes (L-IDs) for accurate grammar (High-quality strategy).
    3. Handle network instability via Circuit Breaker and Retries.
    """

    def __init__(self):
        self.sparql_url = settings.WIKIDATA_SPARQL_URL
        self.circuit_breaker = get_circuit_breaker("wikidata")
        # Headers are important for Wikidata to not block the request
        self.headers = {
            "User-Agent": f"{settings.APP_NAME}/2.0 (Abstract Wiki Architect Bot)"
        }

    async def get_lexemes_by_concept(self, qid: str, lang_code: str) -> List[LexiconEntry]:
        """
        Retrieves lexemes linked to a specific concept (QID).
        Wrapper that applies the Circuit Breaker pattern.
        """
        try:
            # [FIX] Use the async version of the circuit breaker call to prevent blocking
            return await self.circuit_breaker.a_call(self.fetch_lexemes, qid, lang_code)
        except CircuitBreakerOpenError:
            logger.warning("wikidata_circuit_open", qid=qid, lang=lang_code)
            return []
        except Exception as e:
            logger.error("wikidata_fetch_failed", qid=qid, error=str(e))
            return []

    # --- Async Implementation ---

    @retry_external_api
    async def fetch_lexemes(self, qid: str, lang_code: str) -> List[LexiconEntry]:
        """
        Async fetch method with manual retry/circuit logic integration.
        NOTE: The @retry_external_api decorator must be async-aware for this to work 
        correctly with 'await'.
        """
        if self.circuit_breaker.state == "open":
            logger.warning("skipping_wikidata_call", reason="circuit_open")
            return []

        query = self._build_sparql_query(qid, lang_code)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    self.sparql_url, 
                    params={"query": query, "format": "json"},
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                return self._parse_sparql_response(data, qid)
            
            except httpx.HTTPError as e:
                # Let the circuit breaker record the failure
                # (In a full implementation, you'd hook this into the CB state)
                logger.error("wikidata_http_error", url=self.sparql_url, error=str(e))
                raise e

    def _build_sparql_query(self, qid: str, lang_code: str) -> str:
        """
        Constructs a SPARQL query to find Lexemes for a QID.
        """
        # Note: This is a simplified query. Real Wikidata mapping requires 
        # mapping ISO codes to Wikidata Language Items (e.g., 'en' -> Q1860).
        # For now, we fallback to fetching labels if no lexemes are found.
        
        return f"""
        SELECT ?lemma ?langLabel WHERE {{
          wd:{qid} rdfs:label ?lemma .
          FILTER (lang(?lemma) = "{lang_code}")
        }}
        """

    def _parse_sparql_response(self, data: Dict[str, Any], source_qid: str) -> List[LexiconEntry]:
        """
        Converts raw SPARQL JSON into Domain Entities.
        """
        results = []
        bindings = data.get("results", {}).get("bindings", [])
        
        for item in bindings:
            lemma_value = item.get("lemma", {}).get("value")
            
            if lemma_value:
                entry = LexiconEntry(
                    lemma=lemma_value,
                    pos="N", # Defaulting to Noun if we only fetch labels
                    source="wikidata",
                    features={"qid": source_qid}
                )
                results.append(entry)
                
        return results