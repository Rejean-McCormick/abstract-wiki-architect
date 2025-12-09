import os
import sys
import glob
import textwrap
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables (API Key)
load_dotenv()

# --- CONFIGURATION ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GF_GENERATED_PATH = os.path.join("gf", "generated", "src")
GF_CONTRIB_PATH = os.path.join("gf", "contrib")

# System Prompt for the AI Linguist
SYSTEM_PROMPT = """You are an expert computational linguist specializing in Grammatical Framework (GF). 
Your task is to upgrade a "Pidgin" (simplified) grammar implementation into a linguistically accurate one.

The input will be three GF files:
1. Res{Lang}.gf (Resource: Parameters and Types)
2. Syntax{Lang}.gf (Syntax: Clause formation rules)
3. Wiki{Lang}.gf (Concrete: Linearization of AbstractWiki)

The current implementation uses simple string concatenation (String Grammar). 
Your goal is to:
1. Introduce proper parameters (e.g., Number, Gender, Case, Politeness) relevant to the language.
2. Update the 'Noun' and 'Verb' types to use inflection tables.
3. Fix the linearization rules in Syntax module to respect the language's grammar.

Output Format:
You must output the full content of the three files, separated by "### FILE: <filename>".
Do not use markdown code blocks. Just raw text with separators.
"""

def setup_gemini():
    if not GOOGLE_API_KEY:
        print("❌ Error: GOOGLE_API_KEY not found in .env")
        print("   Please add it to run the AI Refiner.")
        sys.exit(1)
    
    genai.configure(api_key=GOOGLE_API_KEY)
    return genai.GenerativeModel('gemini-1.5-pro')

def read_factory_files(iso_code, lang_name):
    """Reads the generated Tier 3 files for context."""
    # Factory folders are usually iso codes or names. 
    # In grammar_factory.py, we use the lowercase ISO code (e.g. 'zul')
    
    target_folder = os.path.join(GF_GENERATED_PATH, iso_code)
    
    if not os.path.exists(target_folder):
        # Fallback search if exact ISO folder doesn't exist
        search_path = os.path.join(GF_GENERATED_PATH, "*")
        candidates = glob.glob(search_path)
        for c in candidates:
            if os.path.basename(c).lower() == lang_name.lower():
                target_folder = c
                break
        else:
            return None

    files = {}
    # Note: grammar_factory uses capitalized names for files: WikiZul.gf
    # We construct the expected filename based on the provided LangName (e.g. Zulu -> WikiZulu.gf)
    # OR based on the ISO code capitalization if that's the convention.
    # Architecture V2 says: WikiZul (ISO based).
    # Let's try to find the files flexibly.
    
    for ext in ["Res", "Syntax", "Wiki"]:
        # Try finding the file by globbing to handle naming conventions
        pattern = os.path.join(target_folder, f"{ext}*.gf")
        matches = glob.glob(pattern)
        if matches:
            fname = os.path.basename(matches[0])
            with open(matches[0], "r", encoding="utf-8") as f:
                files[fname] = f.read()
    
    return files

def save_refined_files(iso_code, file_data):
    """Saves the AI output to gf/contrib/ (Tier 2)."""
    out_dir = os.path.join(GF_CONTRIB_PATH, iso_code)
    os.makedirs(out_dir, exist_ok=True)
    
    for filename, content in file_data.items():
        with open(os.path.join(out_dir, filename), "w", encoding="utf-8") as f:
            f.write(content.strip())
            
    print(f"✅ Saved refined grammar to {out_dir}")

def parse_ai_response(response_text):
    """Splits the single AI string back into files."""
    files = {}
    current_file = None
    lines = response_text.split('\n')
    buffer = []

    for line in lines:
        if line.strip().startswith("### FILE:"):
            if current_file:
                files[current_file] = "\n".join(buffer)
            current_file = line.replace("### FILE:", "").strip()
            buffer = []
        else:
            buffer.append(line)
            
    if current_file and buffer:
        files[current_file] = "\n".join(buffer)
        
    return files

def refine_language(iso_code, lang_name, specific_instructions=""):
    print(f"🧠 AI Refiner: Upgrading {lang_name} ({iso_code})...")
    
    model = setup_gemini()
    
    # 1. Load context
    files = read_factory_files(iso_code, lang_name)
    if not files:
        print(f"❌ Could not find generated files for {iso_code} in {GF_GENERATED_PATH}")
        return

    # 2. Build Prompt
    user_prompt = f"Language: {lang_name} (ISO: {iso_code})\n"
    if specific_instructions:
        user_prompt += f"Instructions: {specific_instructions}\n"
    
    user_prompt += "\n--- EXISTING CODE ---\n"
    for fname, content in files.items():
        user_prompt += f"\n### FILE: {fname}\n{content}\n"

    # 3. Call AI
    print("   Sending to Gemini (this may take 30s)...")
    try:
        response = model.generate_content(SYSTEM_PROMPT + "\n\n" + user_prompt)
        refined_files = parse_ai_response(response.text)
        
        if not refined_files:
            print("❌ AI returned invalid format. Raw response:")
            print(response.text[:500])
            return

        # 4. Save
        save_refined_files(iso_code, refined_files)
        
    except Exception as e:
        print(f"❌ AI Error: {e}")

if __name__ == "__main__":
    # Example usage: python utils/ai_refiner.py zul Zulu "Zulu is a Bantu language with noun classes."
    if len(sys.argv) < 3:
        print("Usage: python utils/ai_refiner.py <iso_code> <LangName> [instructions]")
        print("Example: python utils/ai_refiner.py zul Zulu")
        sys.exit(1)
        
    code = sys.argv[1]
    name = sys.argv[2]
    instr = sys.argv[3] if len(sys.argv) > 3 else ""
    
    refine_language(code, name, instr)