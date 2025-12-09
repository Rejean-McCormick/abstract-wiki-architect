# architect_http_api/services/grammar_service.py

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Import the offline script logic directly
# This assumes 'utils' is in the PYTHONPATH (which Dockerfile ensures)
from utils.ai_refiner import refine_language 

logger = logging.getLogger(__name__)

class GrammarService:
    """
    Service to trigger offline grammar refinement tasks from the API.
    """
    
    def __init__(self):
        # Thread pool for long-running AI tasks (limit concurrency to avoid rate limits)
        self.executor = ThreadPoolExecutor(max_workers=2)

    async def refine_language_async(self, lang_code: str, language_name: str, instructions: str = ""):
        """
        Runs the AI Refiner in a background thread to avoid blocking the API event loop.
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
        """Wrapper to catch exceptions from the script so the thread doesn't crash silently."""
        try:
            refine_language(code, name, instr)
        except Exception as e:
            logger.error(f"❌ Error during grammar refinement for {code}: {e}")

# Singleton instance
grammar_service = GrammarService()