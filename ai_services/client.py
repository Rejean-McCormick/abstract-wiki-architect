import os
import time
import logging
import google.generativeai as genai
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
# Default to 1.5-pro for reasoning, but allow override (e.g. "gemini-1.5-flash" for speed)
MODEL_NAME = os.getenv("ARCHITECT_AI_MODEL", "gemini-1.5-pro")

# --- Logging Setup ---
logger = logging.getLogger("ai_services")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [AI] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Global Singleton
_model = None

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

def generate(prompt, max_retries=3):
    """
    Robust wrapper for text generation with error handling and backoff.
    
    Args:
        prompt (str): The prompt to send.
        max_retries (int): Retry attempts for transient errors.
        
    Returns:
        str: Generated text content or empty string on failure.
    """
    if not _initialize():
        return ""

    wait_time = 2  # Start with 2 seconds wait

    for attempt in range(1, max_retries + 1):
        try:
            response = _model.generate_content(prompt)
            
            # Check for safety blocks or empty returns
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                logger.warning(f"Blocked: {response.prompt_feedback.block_reason}")
                return ""
                
            return response.text.strip()

        except Exception as e:
            logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
            
            if attempt < max_retries:
                time.sleep(wait_time)
                wait_time *= 2  # Exponential Backoff (2s -> 4s -> 8s)
            else:
                logger.error("AI Generation failed after max retries.")
                return ""
    
    return ""