import os
import google.generativeai as genai
from typing import Optional
import structlog

logger = structlog.get_logger()

class GeminiAdapter:
    """
    Driven Adapter for Google Gemini LLM.
    Supports 'Bring Your Own Key' (BYOK) architecture.
    """
    def __init__(self, user_api_key: Optional[str] = None):
        self.model = None
        self.api_key = None
        self.source = "None"

        # 1. Priority: User provided key (from Request Header)
        # We also check if it's the placeholder string to avoid errors
        if user_api_key and user_api_key != "your_gemini_api_key_here":
            self.api_key = user_api_key
            self.source = "User-Provided"
        
        # 2. Fallback: Server env var
        else:
            env_key = os.getenv("GOOGLE_API_KEY")
            if env_key and env_key != "your_gemini_api_key_here":
                self.api_key = env_key
                self.source = "Server-Default"

        # 3. Validation: If no key, Log Warning but DO NOT CRASH
        if not self.api_key:
            logger.warning("llm_init_skipped", msg="No valid Google API Key found. AI features will be disabled.")
            return

        # Configure the global instance for this session/request
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-pro")
        except Exception as e:
            logger.error("llm_config_failed", error=str(e))
            self.model = None

    def generate_text(self, prompt: str) -> str:
        # Check if model exists before trying to use it
        if not self.model:
            logger.warning("llm_call_skipped", reason="No API Key configured")
            return "Error: AI generation is disabled because no valid Google API Key was found."

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            # Catch "Quota Exceeded" specifically to tell user it's THEIR key
            if "429" in str(e):
                raise ConnectionError(f"Your Gemini API Key quota is exceeded ({self.source}).")
            raise e