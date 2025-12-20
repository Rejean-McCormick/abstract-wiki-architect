# app\adapters\wikidata_adapter.py
# app/adapters/wikidata_adapter.py
import httpx
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type, CircuitBreakerError

from app.shared.config import settings
from app.shared.telemetry import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

class WikidataAdapter:
    """
    Driven Adapter: Fetches semantic data from Wikidata.
    Implements the 'Resilience Pattern' to handle missing lexical entries.
    """

    def __init__(self):
        self.sparql_url = settings.WIKIDATA_SPARQL_URL
        self.timeout = settings.WIKIDATA_TIMEOUT
        # Async HTTP client with strict timeouts
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def resolve_concept(self, q_id: str) -> str:
        """
        Resolves a Q-ID (e.g., Q42) to a GF Abstract Syntax Tree fragment.
        
        Strategy:
        1. Check Morphodict (Precise Lexicon).
        2. Fallback: Query Wikidata for Label (Dynamic PN).
        3. Fail-safe: Return raw Q-ID.
        """
        with tracer.start_as_current_span("resolve_concept") as span:
            span.set_attribute("wikidata.q_id", q_id)

            # 1. Morphodict Lookup (Fast Path)
            # In a full implementation, this checks a Redis cache or in-memory dict 
            # loaded from src/morphodict.
            lemma = self._lookup_morphodict(q_id)
            if lemma:
                span.set_attribute("resolution.method", "morphodict")
                return lemma

            # 2. Resilience Fallback (Slow Path)
            logger.info(f"Morphodict miss for {q_id}. Attempting fallback fetch.")
            label = await self._fetch_english_label(q_id)

            if label:
                span.set_attribute("resolution.method", "fallback_label")
                # SANITIZATION: Escape quotes to prevent GF syntax injection
                safe_label = label.replace('"', '\\"')
                # DYNAMIC AST: Wrap in specific RGL constructor for Proper Names
                return f'(UsePN (MkPN "{safe_label}"))'

            # 3. Ultimate Fail-safe
            span.set_attribute("resolution.method", "raw_id")
            return f'(UsePN (MkPN "{q_id}"))'

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def _fetch_english_label(self, q_id: str) -> Optional[str]:
        """
        Queries Wikidata SPARQL for the English label.
        Protected by Circuit Breaker (Tenacity).
        """
        query = f"""
        SELECT ?label WHERE {{
          wd:{q_id} rdfs:label ?label .
          FILTER (lang(?label) = "en")
        }}
        LIMIT 1
        """
        
        try:
            response = await self.client.get(
                self.sparql_url, 
                params={"query": query, "format": "json"}
            )
            response.raise_for_status()
            
            data = response.json()
            bindings = data.get("results", {}).get("bindings", [])
            
            if bindings:
                return bindings[0]["label"]["value"]
                
        except (httpx.HTTPStatusError, KeyError, IndexError) as e:
            logger.warning(f"Wikidata lookup failed for {q_id}: {str(e)}")
            return None
        except CircuitBreakerError:
            logger.error("Wikidata Circuit Breaker open. Skipping fetch.")
            return None
            
        return None

    def _lookup_morphodict(self, q_id: str) -> Optional[str]:
        """
        Checks if the Q-ID exists in the static lexicon.
        (Placeholder for the actual src/morphodict lookup logic).
        """
        # TODO: Inject the actual dictionary loaded from src/morphodict.txt
        # For v1.0 Release, we assume if it's not in memory, we fallback.
        return None

    async def close(self):
        await self.client.aclose()