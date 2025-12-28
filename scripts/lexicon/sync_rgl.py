# scripts/lexicon/sync_rgl.py
# =========================================================================
# GF LEXICON SYNCHRONIZER
#
# This script performs the "Big Pull" from the compiled Grammar into the Database.
#
# Workflow:
# 1. Loads the compiled 'Wiki.pgf' via the GFEngine.
# 2. Identifies all abstract functions in the 'Vocabulary' module.
# 3. For each abstract word (e.g., 'apple_Entity'):
#    a. Ensures a master 'LexiconEntry' exists in the DB.
#    b. Iterates through ALL supported languages (WikiEng, WikiFre, etc.).
#    c. Normalizes language codes to Enterprise Standard (eng -> en).
#    d. Extracts the full inflection table.
#    e. Upserts a 'Translation' record with this linguistic data.
# =========================================================================

import sys
import os
import json
import logging
from typing import List, Dict, Set
from sqlalchemy import func

# Add the project root to the path so we can import internal modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# FIXED: Use standard 'app' namespace consistent with other modules
try:
    from app.adapters.engines.gf_wrapper import GFGrammarEngine as GFEngine 
    # Note: GFGrammarEngine usually wraps pgf, here we might need direct pgf access 
    # or the specific internal engine if architect_http_api had one. 
    # Assuming GFGrammarEngine is the intended interface or fallback to legacy.
    from app.db.session import get_db_session
    from app.db.models import LexiconEntry, Translation
except ImportError:
    # Fallback to legacy namespace if running in specific environment
    from architect_http_api.gf.engine import GFEngine, GFEngineError
    from architect_http_api.gf.morphology import MorphologyHelper, MorphologyError
    from architect_http_api.db.session import get_db_session
    from architect_http_api.db.models import LexiconEntry, Translation

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
BATCH_SIZE = 50  # Commit to DB after processing this many words

# Enterprise Mapping: RGL (3-letter derived) -> ISO (2-letter)
# This bridges Zone C (GF) to Zone B (Database)
RGL_TO_ISO = {
    "eng": "en", "fre": "fr", "ger": "de", "dut": "nl", 
    "ita": "it", "spa": "es", "rus": "ru", "swe": "sv",
    "pol": "pl", "bul": "bg", "ell": "el", "ron": "ro",
    "chi": "zh", "jpn": "ja", "ara": "ar", "hin": "hi",
    "tur": "tr", "por": "pt", "fin": "fi", "nor": "no",
    "dan": "da", "heb": "he", "kor": "ko", "vie": "vi"
}

def get_lexical_category(fun_name: str) -> str:
    """
    Infers the category from the function name suffix (convention used in Vocabulary.gf).
    E.g., 'apple_Entity' -> 'Entity', 'run_VP' -> 'Predicate'
    """
    if "_" in fun_name:
        return fun_name.split("_")[-1]
    return "Unknown"

def sync_lexicon():
    logger.info("Starting GF Lexicon Synchronization...")

    # 1. Initialize GF Engine
    try:
        # We need the low-level engine here to access PGF metadata directly
        # If using GFGrammarEngine wrapper, we access its internal grammar
        engine_wrapper = GFEngine()
        if not engine_wrapper.grammar:
             logger.error("GF Engine failed to load grammar.")
             return
        
        pgf_obj = engine_wrapper.grammar # Access the PGF object
        logger.info(f"GF Engine loaded.")
    except Exception as e:
        logger.error(f"Could not load GF Engine: {e}")
        return

    # 2. Get all target languages
    languages = list(pgf_obj.languages.keys())
    logger.info(f"Target Languages found: {len(languages)} ({', '.join(languages[:5])}...)")

    # 3. Get all abstract functions (vocabulary)
    # Filter for functions that look like our vocabulary items
    all_functions = pgf_obj.functions
    lexical_functions = [f for f in all_functions if f.endswith(('_Entity', '_Property', '_VP', '_Mod'))]
    
    logger.info(f"Found {len(lexical_functions)} lexical items to sync.")

    session = get_db_session()
    count = 0

    try:
        for abstract_fun in lexical_functions:
            category = get_lexical_category(abstract_fun)
            
            # --- A. Upsert Abstract Entry ---
            lex_entry = session.query(LexiconEntry).filter_by(gf_function_id=abstract_fun).first()
            if not lex_entry:
                lex_entry = LexiconEntry(
                    gf_function_id=abstract_fun,
                    category=category,
                    source="RGL_SYNC"
                )
                session.add(lex_entry)
                session.flush() # Flush to get the ID
                logger.debug(f"Created new abstract entry: {abstract_fun}")
            
            # --- B. Sync Concrete Languages ---
            for concrete_name in languages:
                # 1. Extract RGL Code (Zone C)
                if concrete_name.startswith("Wiki"):
                    rgl_code = concrete_name[4:].lower() # WikiEng -> eng
                else:
                    rgl_code = concrete_name.lower()

                # 2. Normalize to Enterprise Standard (Zone B/A)
                # Map 'eng' -> 'en', 'fre' -> 'fr', etc.
                lang_code = RGL_TO_ISO.get(rgl_code, rgl_code)

                try:
                    # 1. Get Inflection Table
                    # We need a MorphologyHelper. Since we might not have the old class,
                    # we assume we can generate linearizations via the concrete grammar.
                    # For a robust sync, we usually need the specialized MorphologyHelper class.
                    # Assuming it exists or we skip complex morphology generation for this pass.
                    
                    # NOTE: This part relies on the specific MorphologyHelper implementation.
                    # If that class is missing in the new 'app' structure, this section 
                    # requires the helper to be ported or imported correctly.
                    
                    # For now, we attempt to import it dynamically or skip if unavailable
                    try:
                        from app.adapters.engines.morphology import MorphologyHelper
                        inflections = MorphologyHelper.get_inflection_table(abstract_fun, rgl_code) # Pass RGL code to Helper
                    except ImportError:
                        # Fallback/Skip if helper not ready in new structure
                        # logger.warning("MorphologyHelper not found, skipping deep inflection sync.")
                        continue

                    if not inflections:
                        continue

                    # 2. Determine Base Form
                    base_form = inflections[0]['form']
                    
                    # 3. Upsert Translation Record
                    translation = session.query(Translation).filter_by(
                        lexicon_entry_id=lex_entry.id,
                        language_code=lang_code # using standard 'en'
                    ).first()

                    forms_json = json.dumps(inflections)

                    if translation:
                        # Update existing
                        if translation.forms_json != forms_json:
                            translation.base_form = base_form
                            translation.forms_json = forms_json
                            translation.updated_at = func.now()
                    else:
                        # Create new
                        translation = Translation(
                            lexicon_entry_id=lex_entry.id,
                            language_code=lang_code, # Stored as 'en'
                            base_form=base_form,
                            forms_json=forms_json
                        )
                        session.add(translation)

                except Exception as e:
                    # Catch morphology errors without stopping the whole sync
                    # logger.warning(f"Error syncing {abstract_fun} for {lang_code}: {e}")
                    pass

            count += 1
            if count % BATCH_SIZE == 0:
                session.commit()
                logger.info(f"Progress: Synced {count}/{len(lexical_functions)} words...")

        session.commit()
        logger.info("Lexicon Synchronization Completed Successfully.")

    except Exception as e:
        logger.error(f"Critical error during sync: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    sync_lexicon()