import logging
import re
from typing import Optional

import google.generativeai as genai
from app.shared.config import settings
from ai_services.prompts import ARCHITECT_SYSTEM_PROMPT, SURGEON_SYSTEM_PROMPT

# Logger setup
logger = logging.getLogger(settings.OTEL_SERVICE_NAME)

class ArchitectAgent:
    """
    The AI Agent responsible for writing and fixing GF grammars.
    Acts as the 'Human-in-the-loop' replacement for Tier 3 languages.
    """

    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY
        self.model_name = settings.AI_MODEL_NAME
        self._client = None

        if self.api_key:
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model_name)
        else:
            logger.warning("⚠️ GOOGLE_API_KEY not found. The Architect Agent is disabled.")

    def generate_grammar(self, lang_code: str, lang_name: str) -> Optional[str]:
        """
        Generates a fresh Concrete Grammar (*.gf) for a missing language.
        
        Args:
            lang_code: ISO 3-letter code (e.g., 'zul').
            lang_name: English name (e.g., 'Zulu').
            
        Returns:
            Raw GF source code string, or None if disabled/failed.
        """
        if not self._client:
            return None

        logger.info(f"🏗️ The Architect is designing {lang_name} ({lang_code})...")

        try:
            # Construct the prompt using the Frozen System Prompt
            user_prompt = f"Write the concrete grammar for Language: {lang_name} (Code: {lang_code})."
            
            response = self._client.generate_content(
                contents=[
                    {"role": "user", "parts": [ARCHITECT_SYSTEM_PROMPT + "\n\n" + user_prompt]}
                ],
                generation_config={"temperature": 0.2} # Low temp for deterministic code
            )
            
            return self._sanitize_output(response.text)

        except Exception as e:
            logger.error(f"❌ Architect generation failed for {lang_code}: {e}")
            return None

    def repair_grammar(self, broken_code: str, error_log: str) -> Optional[str]:
        """
        The Surgeon: Patches a broken grammar file based on compiler logs.
        """
        if not self._client:
            return None

        logger.info("🚑 The Surgeon is operating on broken grammar...")

        try:
            user_prompt = f"""
            **BROKEN CODE:**
            {broken_code}

            **COMPILER ERROR:**
            {error_log}
            """

            response = self._client.generate_content(
                contents=[
                    {"role": "user", "parts": [SURGEON_SYSTEM_PROMPT + "\n\n" + user_prompt]}
                ]
            )
            
            return self._sanitize_output(response.text)

        except Exception as e:
            logger.error(f"❌ Surgeon repair failed: {e}")
            return None

    def _sanitize_output(self, text: str) -> str:
        """
        Cleans LLM output to ensure only valid GF code remains.
        Removes Markdown code blocks (```gf ... ```).
        """
        # Strip markdown fences
        clean = re.sub(r"```(gf)?", "", text)
        clean = clean.strip()
        
        # Ensure it starts with concrete/resource/interface
        if not any(clean.startswith(k) for k in ["concrete", "resource", "interface"]):
            # Fallback: Try to find the start of the code
            match = re.search(r"(concrete|resource|interface)\s+Wiki", clean)
            if match:
                clean = clean[match.start():]
                
        return clean

# Global Singleton
architect = ArchitectAgent()