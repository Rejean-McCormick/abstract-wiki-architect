# app/shared/resilience.py
import time
import asyncio
import structlog
from enum import Enum
from functools import wraps
from typing import Callable, Any, Dict, Coroutine
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from app.shared.config import settings

logger = structlog.get_logger()

# --- 1. Custom Exceptions ---

class ResilienceError(Exception):
    """Base class for resilience-related errors."""
    pass

class CircuitBreakerOpenError(ResilienceError):
    """Raised when a call is blocked because the Circuit Breaker is OPEN."""
    def __init__(self, service_name: str, reset_timeout: float):
        self.service_name = service_name
        self.reset_timeout = reset_timeout
        super().__init__(f"Circuit Breaker for {service_name} is OPEN. Retrying in {reset_timeout}s.")

# --- 2. Circuit Breaker Implementation ---

class CircuitState(str, Enum):
    CLOSED = "closed"     # Normal operation
    OPEN = "open"         # Failing, blocking requests
    HALF_OPEN = "half_open" # Testing recovery

class CircuitBreaker:
    """
    Implements the Circuit Breaker pattern.
    
    Prevents the system from repeatedly trying to execute an operation 
    that is likely to fail, allowing the external service time to recover.
    """
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Executes the function (Synchronously) if the circuit is CLOSED or HALF-OPEN."""
        self._check_state()

        try:
            result = func(*args, **kwargs)
            self._handle_success()
            return result
        except Exception as e:
            self._handle_failure()
            raise e

    async def a_call(self, func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs) -> Any:
        """
        Executes an async function (Coroutine) if the circuit is CLOSED or HALF-OPEN.
        This is the non-blocking equivalent of call().
        """
        self._check_state()

        try:
            # Await the coroutine
            result = await func(*args, **kwargs)
            self._handle_success()
            return result
        except Exception as e:
            self._handle_failure()
            raise e

    def _check_state(self):
        """Internal logic to check if the circuit allows execution."""
        if self.state == CircuitState.OPEN:
            # Check if enough time has passed to try again (Half-Open)
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
            else:
                # Fail fast
                raise CircuitBreakerOpenError(self.name, self.recovery_timeout)

    def _handle_success(self):
        """Called when a request succeeds. Closes the circuit if it was recovering."""
        if self.state == CircuitState.HALF_OPEN:
            self._reset()

    def _handle_failure(self):
        """Called when a request fails. Increments counter or trips the breaker."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # If we fail immediately after trying to recover, go back to OPEN
            self._transition_to(CircuitState.OPEN)
        elif self.failure_count >= self.failure_threshold:
            self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        self.state = new_state
        logger.warning("circuit_breaker_state_change", 
                       service=self.name, 
                       state=new_state, 
                       failures=self.failure_count)

    def _reset(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        logger.info("circuit_breaker_recovered", service=self.name)

# Registry to hold singleton instances of breakers
_breakers: Dict[str, CircuitBreaker] = {}

def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    if service_name not in _breakers:
        _breakers[service_name] = CircuitBreaker(
            name=service_name,
            failure_threshold=5,
            recovery_timeout=settings.WIKIDATA_TIMEOUT
        )
    return _breakers[service_name]

# --- 3. Retry Policies (Tenacity) ---

def retry_external_api(func):
    """
    Decorator for robust retries on external API calls (e.g., Wikidata).
    Strategy:
    - Wait: Exponential Backoff (1s, 2s, 4s...) up to 10s.
    - Stop: After 5 attempts.
    - Log: Logs retries using structlog.
    """
    return retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        # Only retry on standard IO errors (network), not Logic errors (ValueError)
        retry=retry_if_exception_type((IOError, TimeoutError, ConnectionError)),
        before_sleep=before_sleep_log(logger, "warning"),
        reraise=True
    )(func)