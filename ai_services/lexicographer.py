import json
import logging
import math
from . import client

# Setup Logger
logger = logging.getLogger("ai_services.lexicographer")

def _clean_json_response(response_text):
    """
    Helper to extract raw JSON from potential markdown wrapping.
    """
    if not response_text:
        return None
    
    clean_text = response_text.strip()
    
    if clean_text.startswith("```"):
        first_newline = clean_text.find("\n")
        if first_newline != -1:
            clean_text = clean_text[first_newline+1:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
    return clean_text.strip()

def generate_lexicon(words, lang_name, batch_size=20):
    """
    Generates GF morphology dictionaries for a list of English words.
    
    Args:
        words (list): List of abstract identifiers or English words (e.g. "apple_N", "walk_V").
        lang_name (str): Target language (e.g. "French").
        batch_size (int): Number of words to process per AI call.
        
    Returns:
        dict: A dictionary mapping abstract IDs to GF constructors.
              e.g. { "apple_N": "mkN \"pomme\"" }
    """
    if not words or not lang_name:
        return {}

    full_lexicon = {}
    total_batches = math.ceil(len(words) / batch_size)
    
    logger.info(f"📖 Lexicographer: Processing {len(words)} words in {total_batches} batches for {lang_name}...")

    for i in range(total_batches):
        batch = words[i * batch_size : (i + 1) * batch_size]
        
        prompt = f"""
        Act as an expert lexicographer for Grammatical Framework (GF).
        
        TASK: Generate morphology constructors for the target language: {lang_name}.
        
        INPUT WORDS (Abstract IDs):
        {", ".join(batch)}
        
        INSTRUCTIONS:
        1. Identify the part of speech from the suffix (_N for Noun, _V for Verb, _A for Adjective).
        2. Provide the correct GF constructor string (e.g., mkN, mkV, mkA) with the correct translation string.
        3. If the word is irregular, use the appropriate complex constructor if possible, or simplified string.
        
        OUTPUT FORMAT:
        Return strictly a JSON object mapping the input ID to the GF code.
        Example: {{ "apple_N": "mkN \\"pomme\\"", "good_A": "mkA \\"bon\\"" }}
        """
        
        response = client.generate(prompt)
        clean_json = _clean_json_response(response)
        
        if clean_json:
            try:
                batch_result = json.loads(clean_json)
                if isinstance(batch_result, dict):
                    full_lexicon.update(batch_result)
                    logger.info(f"   Batch {i+1}/{total_batches}: Retrieved {len(batch_result)} entries.")
                else:
                    logger.warning(f"   Batch {i+1} failed: AI returned {type(batch_result)} instead of dict.")
            except json.JSONDecodeError as e:
                logger.error(f"   Batch {i+1} JSON Error: {e}")
        else:
            logger.warning(f"   Batch {i+1} returned empty response.")

    return full_lexicon