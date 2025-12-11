import os
import json
import time
import logging
from . import config
from ai_services import surgeon

# --- Configuration ---
FAILURE_REPORT = os.path.join("data", "reports", "build_failures.json")

# Setup Logger
logger = logging.getLogger("builder.healer")

def run_healing_round():
    """
    Reads the failure report, dispatches the AI Surgeon to fix broken files,
    and applies the patches.
    
    Returns:
        bool: True if any files were patched, False otherwise.
    """
    if not os.path.exists(FAILURE_REPORT):
        logger.info("No failure report found. Skipping healing.")
        return False

    try:
        with open(FAILURE_REPORT, 'r') as f:
            failures = json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Corrupt failure report at {FAILURE_REPORT}")
        return False

    if not failures:
        return False

    logger.info(f"🚑 Healer: Dispatched to fix {len(failures)} casualties...")
    
    patched_count = 0

    for rgl_code, data in failures.items():
        filename = data.get("file")
        error_msg = data.get("reason", "")
        
        if not filename: 
            continue
        
        file_path = os.path.join(config.GF_DIR, filename)
        if not os.path.exists(file_path):
            logger.warning(f"Target file not found: {file_path}")
            continue

        # 1. Read the Broken Code
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                broken_content = f.read()
        except IOError as e:
            logger.error(f"Could not read {filename}: {e}")
            continue

        # 2. Call the AI Surgeon
        fixed_code = surgeon.repair_grammar(rgl_code, broken_content, error_msg)
        
        # 3. Validate and Apply Fix
        if fixed_code and "concrete" in fixed_code:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_code)
                logger.info(f"   ✨ Surgeon patched {filename}")
                patched_count += 1
                
                # Rate limiting to respect API quotas
                time.sleep(1) 
            except IOError as e:
                logger.error(f"   ❌ Failed to write fix for {filename}: {e}")
        else:
            logger.warning(f"   ⚠️  Surgeon failed to repair {filename} (Invalid output).")

    if patched_count > 0:
        logger.info(f"🚑 Healing complete. {patched_count} modules repaired.")
        return True
    
    logger.info("🚑 Healing finished but no files were patched.")
    return False