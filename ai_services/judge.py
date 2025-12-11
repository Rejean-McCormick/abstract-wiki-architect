import json
import logging
from . import client

# Setup Logger
logger = logging.getLogger("ai_services.judge")

def _clean_json_response(response_text):
    """
    Helper to extract raw JSON from potential markdown wrapping.
    e.g., turns "```json\n{...}\n```" into "{...}"
    """
    if not response_text:
        return None
    
    clean_text = response_text.strip()
    
    # Strip markdown code blocks if present
    if clean_text.startswith("```"):
        # Find the first newline to skip "```json"
        first_newline = clean_text.find("\n")
        if first_newline != -1:
            clean_text = clean_text[first_newline+1:]
        
        # Strip trailing "```"
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
    return clean_text.strip()

def generate_gold_standard(concepts, lang_name):
    """
    Generates reference sentences for a list of abstract concepts.
    
    Args:
        concepts (list): List of source strings (English sentences or ASTs).
        lang_name (str): Target language name (e.g., "French").
        
    Returns:
        list: A list of translated strings. Returns empty list on failure.
    """
    if not concepts or not lang_name:
        return []

    prompt = f"""
    Translate the following list of sentences into {lang_name}.
    Ensure the translation is natural but strictly grammatical.
    
    INPUT LIST:
    {json.dumps(concepts)}
    
    INSTRUCTIONS:
    Return ONLY a raw JSON list of strings. No markdown. No explanations.
    Example output: ["Sentence 1", "Sentence 2"]
    """
    
    response = client.generate(prompt)
    clean_json = _clean_json_response(response)

    if not clean_json:
        return []

    try:
        data = json.loads(clean_json)
        if isinstance(data, list):
            return data
        else:
            logger.warning(f"Gold Gen failed: Expected list, got {type(data)}")
            return []
    except json.JSONDecodeError as e:
        logger.error(f"Gold Gen JSON Error: {e}")
        return []

def evaluate_output(source_concept, generated_text, lang_name):
    """
    Scores the quality of the generated text against the source concept.
    
    Args:
        source_concept (str): The intended meaning (English or AST).
        generated_text (str): The text produced by the GF engine.
        lang_name (str): Target language.
        
    Returns:
        dict: { "valid": bool, "score": int, "correction": str, "error": str }
    """
    # Fail fast on empty input
    if not generated_text:
        return {"valid": False, "score": 0, "error": "Empty generation input"}

    prompt = f"""
    Act as a strict linguistic judge for the language: {lang_name}.
    
    TASK: Verify if the GENERATED TEXT correctly matches the SOURCE CONCEPT.
    
    SOURCE CONCEPT: "{source_concept}"
    GENERATED TEXT: "{generated_text}"
    
    EVALUATION CRITERIA:
    1. Is it grammatically correct? (Yes/No)
    2. Does it preserve the meaning? (Yes/No)
    3. If No to either, provide the corrected sentence.
    
    OUTPUT FORMAT:
    Return strictly a JSON object with these keys:
    {{
        "valid": boolean,
        "score": integer (0-10),
        "correction": "string (the corrected sentence or null if perfect)"
    }}
    """
    
    response = client.generate(prompt)
    clean_json = _clean_json_response(response)

    if not clean_json:
        return {"valid": False, "score": 0, "error": "No valid response from AI"}

    try:
        data = json.loads(clean_json)
        
        # Validate schema keys
        required_keys = ["valid", "score"]
        if not all(k in data for k in required_keys):
            return {"valid": False, "score": 0, "error": "Missing keys in AI response"}
            
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Validation JSON Error: {e} | Content: {clean_json[:50]}...")
        return {"valid": False, "score": 0, "error": "JSON parse error"}