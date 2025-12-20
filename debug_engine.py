import asyncio
import sys
import os

# 1. Setup Environment
sys.path.append(os.getcwd())
from app.shared.config import settings
from app.adapters.engines.gf_wrapper import GFGrammarEngine
from app.core.domain.models import SemanticFrame

# Force real grammar usage for this test
settings.USE_MOCK_GRAMMAR = False
settings.FILESYSTEM_REPO_PATH = "/mnt/c/MyCode/AbstractWiki/abstract-wiki-architect/gf"

print("--- Engine Debugger ---")
print(f"Target PGF: {settings.AW_PGF_PATH}")

async def run_test():
    # 2. Initialize Engine
    try:
        engine = GFGrammarEngine()
        print("[OK] Engine initialized.")
    except Exception as e:
        print(f"[FAIL] Engine init crashed: {e}")
        return

    # 3. Define Test Data (The exact payload you sent via curl)
    frame = SemanticFrame(
        frame_type="John",  # Matches the function in your PGF
        subject={}, 
        meta={}
    )
    target_lang = "kor"

    print(f"\nAttempting to generate '{frame.frame_type}' in '{target_lang}'...")

    # 4. Run Generation
    try:
        result = await engine.generate(target_lang, frame)
        print("\n[SUCCESS] Generated Text:")
        print(f"   {result.text}")
        print(f"   (Debug Info: {result.debug_info})")
    except Exception as e:
        print("\n[CRASH] Generation failed!")
        print("Traceback details:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())