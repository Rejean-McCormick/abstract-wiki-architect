import os
import subprocess
import sys

# --- CONFIGURATION: TARGET LANGUAGES ---
# You can list all 300+ ISO 639-3 codes here. 
# The script will filter this list and ONLY build the ones found in the RGL.
RGL_LANGUAGES = [
    # --- Core RGL (Mature) ---
    "eng", "fra", "deu", "spa", "ita", "swe", "por", "rus", "zho", "jpn",
    "ara", "hin", "fin", "est", "swa", "tur", "bul", "pol", "ron", "nld",
    "dan", "nob", "isl", "ell", "heb", "lav", "lit", "mlt", "hun", "cat",
    "eus", "tha", "urd", "fas", "mon", "nep", "pan", "snd", "afr", "amh",
    "kor", "lat", "nno", "slv", "som", "tgl", "vie",
    
    # --- Future / 300 Goal (Placeholders) ---
    # Add your 300+ codes here (e.g., "ibo", "yor", "zul", etc.)
    # The script will skip them nicely if not found in RGL.
]

# --- MAPPINGS: ISO 639-3 -> RGL CONVENTIONS ---

# 1. Map to Legacy 3-Letter RGL Codes (e.g., SyntaxFre.gf)
# If missing, defaults to Capitalized ISO (e.g., est -> Est)
RGL_CODE_MAP = {
    "fra": "Fre", "deu": "Ger", "zho": "Chi", "jpn": "Jap",
    "nld": "Dut", "ell": "Gre", "ron": "Rom", "nob": "Nor",
    "swe": "Swe", "dan": "Dan", "isl": "Ice", "fin": "Fin",
    "bul": "Bul", "pol": "Pol", "rus": "Rus", "spa": "Spa",
    "por": "Por", "ita": "Ita", "eng": "Eng", "hin": "Hin",
    "urd": "Urd", "tha": "Tha", "kor": "Kor", "lav": "Lav",
    "lit": "Lit", "est": "Est", "mlt": "Mlt", "cat": "Cat",
    "eus": "Bas", "hun": "Hun", "ara": "Ara", "swa": "Swa",
    "tur": "Tur", "heb": "Heb", "fas": "Pes", "mon": "Mon",
    "nep": "Nep", "pan": "Pan", "snd": "Snd", "afr": "Afr",
    "amh": "Amh", "lat": "Lat", "nno": "Nno", "slv": "Slv",
    "som": "Som", "tgl": "Tgl", "vie": "Vie"
}

# 2. Map to Source Folder Names (for -path argument)
ISO_TO_RGL_FOLDER = {
    "eng": "english",    "fra": "french",     "deu": "german",
    "spa": "spanish",    "ita": "italian",    "swe": "swedish",
    "por": "portuguese", "rus": "russian",    "zho": "chinese",
    "jpn": "japanese",   "ara": "arabic",     "hin": "hindi",
    "fin": "finnish",    "est": "estonian",   "swa": "swahili",
    "tur": "turkish",    "bul": "bulgarian",  "pol": "polish",
    "ron": "romanian",   "nld": "dutch",      "dan": "danish",
    "nob": "norwegian",  "isl": "icelandic",  "ell": "greek",
    "heb": "hebrew",     "lav": "latvian",    "lit": "lithuanian",
    "mlt": "maltese",    "hun": "hungarian",  "cat": "catalan",
    "eus": "basque",     "tha": "thai",       "urd": "urdu",
    "fas": "persian",    "mon": "mongolian",  "nep": "nepali",
    "pan": "punjabi",    "snd": "sindhi",     "afr": "afrikaans",
    "amh": "amharic",    "kor": "korean",     "lat": "latin",
    "nno": "nynorsk",    "slv": "slovenian",  "som": "somali",
    "tgl": "tagalog",    "vie": "vietnamese"
}

# 3. Map to Shared Libraries (Important for compiling families like Romance)
ISO_TO_SHARED_LIB = {
    "fra": "romance", "spa": "romance", "ita": "romance", 
    "por": "romance", "ron": "romance", "cat": "romance",
    "swe": "scandinavian", "dan": "scandinavian", "nob": "scandinavian", 
    "nno": "scandinavian",
    "fin": "uralic", "est": "uralic"
}

GF_DIR = os.path.dirname(os.path.abspath(__file__))
PGF_OUTPUT_FILE = os.path.join(GF_DIR, "Wiki.pgf")
ABSTRACT_NAME = "AbstractWiki"

# --- LEXICON PLACEHOLDERS ---
# (In a real system, you'd load this from a DB or CSV)
LEXICON_DATA = {
    "lex_animal_N": {"eng": "animal", "fra": "animal"},
    # ... (Your full dictionary here) ...
}
FALLBACKS = {"_N": "dummy", "_A": "dummy", "_V": "dummy", "_Adv": "dummy"}

# --- HELPERS ---

def get_rgl_name(iso_code: str) -> str:
    return RGL_CODE_MAP.get(iso_code, iso_code.capitalize())

def check_rgl_availability(iso_code: str, rgl_base_path: str) -> bool:
    """
    Checks if the RGL folder for this language actually exists.
    This prevents the build from crashing on 'missing file' errors.
    """
    folder_name = ISO_TO_RGL_FOLDER.get(iso_code)
    if not folder_name:
        return False
    
    full_path = os.path.join(rgl_base_path, folder_name)
    return os.path.isdir(full_path)

def get_word(ident: str, iso_code: str) -> str:
    # 1. Exact match
    if ident in LEXICON_DATA and iso_code in LEXICON_DATA[ident]:
        return LEXICON_DATA[ident][iso_code]
    
    # 2. English fallback (if available)
    if "eng" in LEXICON_DATA.get(ident, {}):
        word = LEXICON_DATA[ident]["eng"]
        # Basic heuristic to avoid morphology crashes on fallback words
        if iso_code == "fra" and ident.endswith("_V"): return "marcher"
        return word

    # 3. Dummy fallback
    suffix = ident.split("_")[-1]
    return FALLBACKS.get("_" + suffix, "dummy")

# --- GENERATION LOGIC ---

def generate_abstract_wiki():
    """Generates AbstractWiki.gf"""
    filename = f"{ABSTRACT_NAME}.gf"
    content = f"""abstract {ABSTRACT_NAME} = {{
  cat
    Entity ; Property ; Fact ; Predicate ; Modifier ; Value ;

  fun
    mkFact : Entity -> Predicate -> Fact ;
    mkIsAProperty : Entity -> Property -> Fact ;
    FactWithMod : Fact -> Modifier -> Fact ;
    mkLiteral : Value -> Entity ;

    Entity2NP : Entity -> Entity ;
    Property2AP : Property -> Property ;
    VP2Predicate : Predicate -> Predicate ;

    -- Vocabulary
"""
    # Just generate some example vocabulary stubs for the Abstract
    # (In production, iterate over ALL keys in your comprehensive DB)
    for ident in LEXICON_DATA.keys():
        if ident.endswith("_N"):
            fun_name = ident.replace("lex_", "").replace("_N", "_Entity")
            content += f"    {fun_name} : Entity ;\n"
        elif ident.endswith("_A"):
            fun_name = ident.replace("lex_", "").replace("_A", "_Property")
            content += f"    {fun_name} : Property ;\n"
        elif ident.endswith("_V"):
            fun_name = ident.replace("lex_", "").replace("_V", "_VP")
            content += f"    {fun_name} : Predicate ;\n"
        elif ident.endswith("_Adv"):
            fun_name = ident.replace("lex_", "").replace("_Adv", "_Mod")
            content += f"    {fun_name} : Modifier ;\n"

    content += "}\n"
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f:
        f.write(content)
    return filename

def generate_wiki_interface():
    """Generates WikiI.gf"""
    filename = "WikiI.gf"
    content = f"""incomplete concrete WikiI of {ABSTRACT_NAME} = open Syntax in {{
  lincat
    Entity = NP ; Property = AP ; Fact = S ; 
    Predicate = VP ; Modifier = Adv ; Value = {{s : Str}} ;

  lin
    mkFact entity predicate = mkS (mkCl entity predicate) ;
    mkIsAProperty entity property = mkS (mkCl entity (mkVP property)) ;
    FactWithMod fact modifier = mkS modifier fact ;

    Entity2NP e = e ;
    Property2AP p = p ;
    VP2Predicate p = p ;
}}
"""
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f:
        f.write(content)
    return filename

def generate_dictionary_file(iso_code: str) -> str:
    rgl_name = get_rgl_name(iso_code)
    filename = f"Dict{rgl_name}.gf"
    
    oper_lines = []
    for ident in LEXICON_DATA.keys():
        word = get_word(ident, iso_code)
        if ident.endswith("_N"):
            oper_lines.append(f"    {ident} = mkN \"{word}\" ;")
        elif ident.endswith("_A"):
            oper_lines.append(f"    {ident} = mkA \"{word}\" ;")
        elif ident.endswith("_V"):
            oper_lines.append(f"    {ident} = mkV \"{word}\" ;")
        elif ident.endswith("_Adv"):
            oper_lines.append(f"    {ident} = mkAdv \"{word}\" ;")

    content = f"""resource Dict{rgl_name} = open Paradigms{rgl_name} in {{
  oper
{chr(10).join(oper_lines)}
}} ;
"""
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f:
        f.write(content)
    return filename

def generate_concrete_file(iso_code: str) -> str:
    rgl_name = get_rgl_name(iso_code)
    filename = f"Wiki{rgl_name}.gf"
    
    lin_rules = []
    for ident in LEXICON_DATA.keys():
        if ident.endswith("_N"):
            abs_fun = ident.replace("lex_", "").replace("_N", "_Entity")
            lin_rules.append(f"    {abs_fun} = mkNP {ident} ;")
        elif ident.endswith("_A"):
            abs_fun = ident.replace("lex_", "").replace("_A", "_Property")
            lin_rules.append(f"    {abs_fun} = mkAP {ident} ;")
        elif ident.endswith("_V"):
            abs_fun = ident.replace("lex_", "").replace("_V", "_VP")
            lin_rules.append(f"    {abs_fun} = mkVP {ident} ;")
        elif ident.endswith("_Adv"):
            abs_fun = ident.replace("lex_", "").replace("_Adv", "_Mod")
            lin_rules.append(f"    {abs_fun} = {ident} ;")

    lin_rules.append("    mkLiteral v = symb v.s ;")

    content = f"""concrete Wiki{rgl_name} of {ABSTRACT_NAME} = WikiI ** open Syntax{rgl_name}, Paradigms{rgl_name}, Symbolic{rgl_name}, Dict{rgl_name} in {{
  lin
{chr(10).join(lin_rules)}
}} ;
"""
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f:
        f.write(content)
    return filename

def compile_gf(concrete_files: list[str], active_iso_codes: list[str]):
    print(f"--- Compiling {len(concrete_files)} files into {PGF_OUTPUT_FILE} ---")
    
    # 1. Determine base path
    rgl_base = os.environ.get("GF_LIB_PATH", "/usr/local/lib/gf")
    
    # 2. Build the search path
    # Standard folders
    search_paths = [
        rgl_base,
        os.path.join(rgl_base, "api"),
        os.path.join(rgl_base, "prelude"),
        os.path.join(rgl_base, "abstract"),
        os.path.join(rgl_base, "common"),
    ]
    
    # Language-specific folders
    for code in active_iso_codes:
        folder = ISO_TO_RGL_FOLDER.get(code)
        if folder:
            search_paths.append(os.path.join(rgl_base, folder))
            
    # Shared libraries (Romance, Scandinavian, etc.)
    # We add these automatically if any active language needs them
    for code in active_iso_codes:
        shared = ISO_TO_SHARED_LIB.get(code)
        if shared:
            shared_path = os.path.join(rgl_base, shared)
            if shared_path not in search_paths:
                search_paths.append(shared_path)

    path_arg = ":".join(search_paths)
    
    # 3. Run Compiler
    command = ["gf", "-make", "-path", path_arg] + concrete_files
    
    try:
        env = os.environ.copy()
        subprocess.run(command, check=True, cwd=GF_DIR, env=env)
        print("GF Compilation successful.")
        
        generated_pgf = os.path.join(GF_DIR, f"{ABSTRACT_NAME}.pgf")
        if os.path.exists(generated_pgf):
            if os.path.exists(PGF_OUTPUT_FILE):
                os.remove(PGF_OUTPUT_FILE)
            os.rename(generated_pgf, PGF_OUTPUT_FILE)
            print(f"✅ Final PGF written to: {PGF_OUTPUT_FILE}")
        else:
            print(f"Error: Expected output {generated_pgf} was not found.")
            sys.exit(1)
            
    except subprocess.CalledProcessError:
        print("❌ GF Compilation failed!")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ GF compiler not found. Ensure 'gf' is in your PATH.")
        sys.exit(1)

def main():
    print("GF Multilingual Build Script Starting...")
    
    rgl_base = os.environ.get("GF_LIB_PATH", "/usr/local/lib/gf")
    print(f"Checking RGL in: {rgl_base}")

    generate_abstract_wiki()
    generate_wiki_interface()

    concrete_files = []
    active_iso_codes = []

    # Filter languages: Only build if RGL folder exists
    for iso_code in RGL_LANGUAGES:
        if check_rgl_availability(iso_code, rgl_base):
            try:
                generate_dictionary_file(iso_code)
                concrete_files.append(generate_concrete_file(iso_code))
                active_iso_codes.append(iso_code)
            except Exception as e:
                print(f"Warning: Failed generating files for {iso_code}: {e}")
        else:
            print(f"Skipping {iso_code}: RGL folder not found.")
            
    print(f"Successfully prepared {len(active_iso_codes)} supported languages.")
    
    if concrete_files:
        compile_gf(concrete_files, active_iso_codes)
    else:
        print("No valid languages found to compile.")

if __name__ == "__main__":
    main()