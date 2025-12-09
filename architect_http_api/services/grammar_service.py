# architect_http_api/services/grammar_service.py
import logging
import asyncio
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

# Import the offline script logic directly
# Ensure 'utils' is in your PYTHONPATH or accessible relative to the app execution
from utils.ai_refiner import refine_language 

logger = logging.getLogger(__name__)

class GrammarService:
    """
    Service to trigger offline grammar refinement tasks from the API.
    """
    
    def __init__(self):
        # Thread pool for long-running AI tasks
        self.executor = ThreadPoolExecutor(max_workers=2)

    async def refine_language_async(self, lang_code: str, language_name: str, instructions: str = ""):
        """
        Runs the AI Refiner in a background thread to avoid blocking the API.
        """
        logger.info(f"🚀 Triggering AI Refinement for {language_name} ({lang_code})...")
        
        loop = asyncio.get_running_loop()
        
        # Run the synchronous 'refine_language' function in a separate thread
        await loop.run_in_executor(
            self.executor, 
            self._run_refiner_safe, 
            lang_code, 
            language_name, 
            instructions
        )
        
        logger.info(f"✅ AI Refinement task for {lang_code} finished.")

    def _run_refiner_safe(self, code: str, name: str, instr: str):
        """Wrapper to catch exceptions from the script."""
        try:
            refine_language(code, name, instr)
        except Exception as e:
            logger.error(f"❌ Error during grammar refinement for {code}: {e}")

# Singleton
grammar_service = GrammarService()