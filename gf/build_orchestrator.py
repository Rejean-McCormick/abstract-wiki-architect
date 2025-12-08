import os
import subprocess
import sys

# ===========================================================================
# CONFIGURATION
# ===========================================================================

# The Master List of ISO 639-3 codes to support.
# This combines Official RGL languages + Factory languages.
TARGET_LANGUAGES = [
    # --- Tier 1: Core RGL (Mature) ---
    "eng", "fra", "deu", "spa", "ita", "swe", "por", "rus", "zho", "jpn",
    "ara", "hin", "fin", "est", "swa", "tur", "bul", "pol", "ron", "nld",
    "dan", "nob", "isl", "ell", "heb", "lav", "lit", "mlt", "hun", "cat",
    "eus", "tha", "urd", "fas", "mon", "nep", "pan", "snd", "afr", "amh",
    "kor", "lat", "nno", "slv", "som", "tgl", "vie",

    # --- Tier 3: Factory / Generated (Examples) ---
    # Add your 260+ extra codes here. 
    "zul", "yor", "ibo", "hau", "wol", "kin", "ind", "msa", "que", "nav",
    "aym", "grn", "fry", "bre", "oci", "gla", "nah", "tat", "kur", "uzb",
    "kaz", "ben", "tam", "tel", "jav", "lug", "lin", "xho"
]

# Mapping ISO 639-3 to GF Concrete Name Suffix (WikiXXX).
# Most use Capitalized ISO (e.g. zul -> Zul), but RGL has legacy names (fra -> Fre).
CODE_TO_NAME = {
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
    "som": "Som", "tgl": "Tgl", "vie": "Vie",
    "msa": "Msa" 
}

# Mapping ISO 639-3 to Official RGL Source Folder Name
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

# Shared Libraries required for certain RGL families
ISO_TO_SHARED_LIB = {
    "fra": "romance", "spa": "romance", "ita": "romance", 
    "por": "romance", "ron": "romance", "cat": "romance",
    "swe": "scandinavian", "dan": "scandinavian", "nob": "scandinavian", 
    "nno": "scandinavian",
    "fin": "uralic", "est": "uralic"
}

# Mapping ISO 639-3 to Factory Folder Name.
# Since our factory generates folders based on full language names (e.g. "zulu"),
# we map codes to those names here.
ISO_TO_FACTORY_FOLDER = {
    "zul": "zulu", "yor": "yoruba", "ibo": "igbo", "hau": "hausa",
    "wol": "wolof", "kin": "kinyarwanda", "kor": "korean",
    "ind": "indonesian", "msa": "malay", "tgl": "tagalog", "vie": "vietnamese",
    "que": "quechua", "nav": "navajo", "aym": "aymara", "grn": "guarani",
    "fry": "frisian", "bre": "breton", "oci": "occitan", "gla": "gaelic",
    "nah": "nahuatl", "tat": "tatar", "kur": "kurdish", "xho": "xhosa",
    "lug": "ganda", "lin": "lingala", "som": "somali", "jav": "javanese",
    "tam": "tamil", "tel": "telugu", "ben": "bengali", "uzb": "uzbek",
    "kaz": "kazakh"
}

GF_DIR = os.path.dirname(os.path.abspath(__file__))
PGF_OUTPUT_FILE = os.path.join(GF_DIR, "Wiki.pgf")
ABSTRACT_NAME = "AbstractWiki"

# ===========================================================================
# GENERATORS
# ===========================================================================

def get_gf_suffix(iso_code):
    """Returns the suffix used for the concrete grammar (e.g. 'Fre' or 'Zul')."""
    return CODE_TO_NAME.get(iso_code, iso_code.capitalize())

def generate_abstract():
    """Generates the Abstract Syntax file."""
    filename = f"{ABSTRACT_NAME}.gf"
    content = f"""abstract {ABSTRACT_NAME} = {{
  cat Entity; Property; Fact; Predicate; Modifier; Value;
  fun
    mkFact : Entity -> Predicate -> Fact;
    mkIsAProperty : Entity -> Property -> Fact;
    FactWithMod : Fact -> Modifier -> Fact;
    mkLiteral : Value -> Entity;
    Entity2NP : Entity -> Entity; Property2AP : Property -> Property; VP2Predicate : Predicate -> Predicate;
    
    -- Vocabulary Stubs (Shared across all languages)
    lex_animal_N : Entity; lex_cat_N : Entity; lex_walk_V : Predicate; lex_blue_A : Property;
}}\n"""
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f: 
        f.write(content)
    return filename

def generate_interface():
    """Generates the Interface file used by RGL languages."""
    filename = "WikiI.gf"
    content = f"""incomplete concrete WikiI of {ABSTRACT_NAME} = open Syntax in {{
  lincat Entity = NP; Property = AP; Fact = S; Predicate = VP; Modifier = Adv; Value = {{s : Str}};
  lin
    mkFact s p = mkS (mkCl s p);
    mkIsAProperty s p = mkS (mkCl s (mkVP p));
    FactWithMod f m = mkS m f;
    Entity2NP x = x; Property2AP x = x; VP2Predicate x = x;
}}\n"""
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f: 
        f.write(content)
    return filename

def generate_rgl_connector(iso_code):
    """Generates the connector file that bridges Official RGL to our AbstractWiki."""
    suffix = get_gf_suffix(iso_code)
    filename = f"Wiki{suffix}.gf"
    # Note: We use mkNP/mkVP from RGL Paradigms here
    content = f"""concrete Wiki{suffix} of {ABSTRACT_NAME} = WikiI ** open Syntax{suffix}, Paradigms{suffix}, Symbolic{suffix} in {{
  lin
    lex_animal_N = mkNP (mkN "animal");
    lex_cat_N = mkNP (mkN "cat");
    lex_walk_V = mkVP (mkV "walk");
    lex_blue_A = mkAP (mkA "blue");
    mkLiteral v = symb v.s;
}};\n"""
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f: 
        f.write(content)
    return filename

# ===========================================================================
# MAIN BUILD LOGIC
# ===========================================================================

def main():
    print("🚀 Abstract Wiki Architect: Orchestrating 300-Language Build...")
    
    # 1. Define Base Paths
    # These match the Docker container structure
    rgl_base = os.environ.get("GF_LIB_PATH", "/usr/local/lib/gf")
    contrib_base = "/usr/local/lib/gf/contrib" 
    factory_base = "/usr/local/lib/gf/generated"

    # 2. Generate Base Files
    generate_abstract()
    generate_interface()

    files_to_compile = []
    # Base search paths for the compiler (Core RGL)
    search_paths = [
        rgl_base, 
        os.path.join(rgl_base, "api"), 
        os.path.join(rgl_base, "prelude"), 
        os.path.join(rgl_base, "abstract"), 
        os.path.join(rgl_base, "common")
    ]

    # 3. Waterfall Logic: Iterate Languages
    for iso_code in TARGET_LANGUAGES:
        suffix = get_gf_suffix(iso_code)
        target_file = f"Wiki{suffix}.gf"
        
        # --- Priority 1: Contrib (Manual Overrides) ---
        contrib_file_path = os.path.join(contrib_base, iso_code, target_file)
        # Note: We check if the folder exists in the container path, or relative in local dev
        # For simplicity, we assume we are running in Docker or structure matches.
        
        # Local dev fallback for paths
        if not os.path.exists(contrib_base):
             # Fallback to local project path if running outside docker
             local_contrib = os.path.join(GF_DIR, "contrib")
             contrib_file_path = os.path.join(local_contrib, iso_code, target_file)

        if os.path.exists(contrib_file_path):
            print(f"[{iso_code}] Using Tier 2: Manual Contrib")
            files_to_compile.append(contrib_file_path)
            # Add this specific language folder to path
            search_paths.append(os.path.dirname(contrib_file_path))
            continue

        # --- Priority 2: Factory (Generated) ---
        folder = ISO_TO_FACTORY_FOLDER.get(iso_code)
        if folder:
            factory_file_path = os.path.join(factory_base, folder, target_file)
            
            # Local dev fallback
            if not os.path.exists(factory_base):
                local_factory = os.path.join(GF_DIR, "generated", "src")
                factory_file_path = os.path.join(local_factory, folder, target_file)

            if os.path.exists(factory_file_path):
                print(f"[{iso_code}] Using Tier 3: Factory Generated")
                files_to_compile.append(factory_file_path)
                # Add factory root to path so 'open ResZul' works
                search_paths.append(os.path.dirname(factory_file_path))
                continue
            
        # --- Priority 3: Official RGL ---
        rgl_folder = ISO_TO_RGL_FOLDER.get(iso_code)
        if rgl_folder:
            full_rgl_path = os.path.join(rgl_base, rgl_folder)
            
            # Check for critical Syntax file to ensure it's a valid RGL lang
            syntax_file = f"Syntax{suffix}.gf"
            
            if os.path.exists(os.path.join(full_rgl_path, syntax_file)) or \
               os.path.exists(os.path.join(rgl_base, "api", syntax_file)):
                
                print(f"[{iso_code}] Using Tier 1: Official RGL")
                # For RGL, we generate the connector file in the root GF_DIR
                files_to_compile.append(generate_rgl_connector(iso_code))
                search_paths.append(full_rgl_path)
                
                # Add shared libs (Romance, Scandinavian, etc.)
                shared = ISO_TO_SHARED_LIB.get(iso_code)
                if shared:
                    search_paths.append(os.path.join(rgl_base, shared))
            else:
                print(f"⚠️  [{iso_code}] SKIPPING: RGL found, but {syntax_file} missing.")
        else:
            print(f"⚠️  [{iso_code}] SKIPPING: No source found (RGL, Contrib, or Factory).")

    # 4. Compile
    if not files_to_compile:
        print("❌ Error: No files found to compile. Check your configuration.")
        sys.exit(1)

    print(f"\n--- Starting Compilation of {len(files_to_compile)} languages ---")
    
    # Deduplicate search paths to keep command clean
    search_paths = list(set(search_paths))
    path_arg = ":".join(search_paths)
    
    # GF Command
    cmd = ["gf", "-make", "-path", path_arg] + files_to_compile
    
    try:
        # Run compilation
        env = os.environ.copy()
        subprocess.run(cmd, check=True, cwd=GF_DIR, env=env)
        
        # Rename output to standard name
        generated_pgf = os.path.join(GF_DIR, f"{ABSTRACT_NAME}.pgf")
        if os.path.exists(generated_pgf):
            if os.path.exists(PGF_OUTPUT_FILE):
                os.remove(PGF_OUTPUT_FILE)
            os.rename(generated_pgf, PGF_OUTPUT_FILE)
            print(f"✅ SUCCESS: Grammar compiled to {PGF_OUTPUT_FILE}")
        else:
            print("❌ Compile failed: PGF binary was not created.")
            sys.exit(1)
            
    except subprocess.CalledProcessError:
        print("❌ Compile failed due to GF errors.")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ GF Compiler not found. Ensure 'gf' is in PATH.")
        sys.exit(1)

if __name__ == "__main__":
    main()