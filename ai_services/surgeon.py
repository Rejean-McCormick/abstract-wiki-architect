import logging
from . import client

# Setup Logger
logger = logging.getLogger("ai_services.surgeon")

def _clean_gf_response(response_text):
    """
    Helper to extract raw GF code from markdown wrapping.
    """
    if not response_text:
        return None
    
    clean_text = response_text.strip()
    
    # Strip markdown code blocks
    if clean_text.startswith("```"):
        # Find newline after ```gf or ```
        first_newline = clean_text.find("\n")
        if first_newline != -1:
            clean_text = clean_text[first_newline+1:]
        
        # Strip trailing ```
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
    return clean_text.strip()

def repair_grammar(rgl_code, file_content, error_log):
    """
    Surgically repairs broken GF code based on compiler error logs.
    
    Args:
        rgl_code (str): The 3-letter RGL language code (e.g., "Amh").
        file_content (str): The content of the broken .gf file.
        error_log (str): The specific error message from the GF compiler.
        
    Returns:
        str: The fixed GF code, or None if repair failed.
    """
    logger.info(f"🤖 Surgeon: Analyzing compilation failure for {rgl_code}...")

    # Fail fast on empty inputs
    if not file_content or not error_log:
        logger.warning("Surgeon aborted: Missing file content or error log.")
        return None

    prompt = f"""
    You are an expert in Grammatical Framework (GF) and the Resource Grammar Library (RGL).
    
    CONTEXT:
    I am building a concrete syntax file (Wiki{rgl_code}.gf).
    The build failed.
    
    THE ERROR LOG:
    {error_log}
    
    THE BROKEN CODE:
    {file_content}
    
    YOUR MISSION:
    1. Analyze the error. 
       - If it says "constant not found" (e.g. mkNP, mkCN), the standard API is missing for this language. You MUST replace these with lower-level constructors like 'MassNP', 'DetCN', 'UseN', or 'UsePN' found in Noun{rgl_code} or Cat{rgl_code}.
       - If it is a type mismatch, adjust the parameters to match the expected record type.
    2. Fix the code to make it compile.
    
    OUTPUT FORMAT:
    Return ONLY the full, corrected source code. 
    Do not write explanations. 
    Do not use Markdown formatting.
    """

    response_text = client.generate(prompt)
    fixed_code = _clean_gf_response(response_text)
    
    # Validation: Ensure it looks like a concrete grammar
    if fixed_code and "concrete" in fixed_code and "open" in fixed_code:
        return fixed_code
    else:
        logger.error(f"Surgeon failed: AI returned invalid or empty code for {rgl_code}")
        return None