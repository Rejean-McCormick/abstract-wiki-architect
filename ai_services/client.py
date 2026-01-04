# ai_services\client.py
import os
import time
import asyncio
import logging
import google.generativeai as genai
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
# Default to 1.5-pro for reasoning, but allow override (e.g. "gemini-1.5-flash" for speed)
MODEL_NAME = os.getenv("ARCHITECT_AI_MODEL", "gemini-2.0-flash")

# --- Logging Setup ---
logger = logging.getLogger("ai_services")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [AI] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# --- Circuit Breaker Pattern ---
class CircuitBreakerOpen(Exception):
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning("🔥 Circuit Breaker OPENED. AI Service paused.")

    def record_success(self):
        if self.state != "CLOSED":
            logger.info("✅ Circuit Breaker RECOVERED.")
        self.failures = 0
        self.state = "CLOSED"

    def check(self):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True # Try one request
            raise CircuitBreakerOpen("AI Service is temporarily down.")
        return True

# Global Singletons
_model = None
_breaker = CircuitBreaker()

def _initialize():
    """Initializes the Gemini client (Singleton Pattern)."""
    global _model
    if _model:
        return True
    
    if not API_KEY:
        logger.error("Missing GOOGLE_API_KEY in environment variables.")
        return False

    try:
        genai.configure(api_key=API_KEY)
        _model = genai.GenerativeModel(MODEL_NAME)
        logger.info(f"Connected to Google AI ({MODEL_NAME})")
        return True
    except Exception as e:
        logger.critical(f"Connection failed: {e}")
        return False

async def generate_async(prompt, max_retries=3):
    """
    Robust ASYNC wrapper for text generation with Circuit Breaker and Backoff.
    
    Args:
        prompt (str): The prompt to send.
        max_retries (int): Retry attempts for transient errors.
        
    Returns:
        str: Generated text content or empty string on failure.
    """
    # 1. Init Check
    if not _initialize():
        return ""

    # 2. Circuit Breaker Check
    try:
        _breaker.check()
    except CircuitBreakerOpen:
        logger.error("Request blocked by Circuit Breaker.")
        return ""

    wait_time = 2  # Start with 2 seconds wait

    for attempt in range(1, max_retries + 1):
        try:
            # 3. Non-blocking Execution
            # We run the blocking synchronous Google API call in a separate thread
            response = await asyncio.to_thread(_model.generate_content, prompt)
            
            # Check for safety blocks or empty returns
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                logger.warning(f"Blocked: {response.prompt_feedback.block_reason}")
                return ""
            
            # Success!
            _breaker.record_success()
            return response.text.strip()

        except Exception as e:
            logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
            _breaker.record_failure()
            
            if attempt < max_retries:
                # 4. Async Sleep (doesn't block the API)
                await asyncio.sleep(wait_time)
                wait_time *= 2  # Exponential Backoff (2s -> 4s -> 8s)
            else:
                logger.error("AI Generation failed after max retries.")
                return ""
    
    return ""

def generate(prompt, max_retries=3):
    """
    Synchronous wrapper for legacy CLI tools (e.g. forge.py).
    WARNING: Do not use this in the FastAPI app, use generate_async instead.
    """
    return asyncio.run(generate_async(prompt, max_retries))