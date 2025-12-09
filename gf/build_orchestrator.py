import os
import subprocess
import sys
import shutil

# ===========================================================================
# CONFIGURATION
# ===========================================================================

# The Master List of ISO 639-3 codes to support.
TARGET_LANGUAGES = [
    # --- Tier 1: Core RGL (Mature) ---
    "eng", "fra", "deu", "spa", "ita", "swe", "por", "rus", "zho", "jpn",
    "ara", "hin", "fin", "est", "swa", "tur", "bul", "pol", "ron", "nld",
    "dan", "nob", "isl", "ell", "heb", "lav", "lit", "mlt", "hun", "cat",
    "eus", "tha", "urd", "fas", "mon", "nep", "pan", "snd", "afr", "amh",
    "kor", "lat", "nno", "slv", "som", "tgl", "vie",

    # --- Tier 3: Factory / Generated (Examples) ---
    "zul", "yor", "ibo", "hau", "wol", "kin", "ind", "msa", "que", "nav",
    "aym", "grn", "fry", "bre", "oci", "gla", "nah", "tat", "kur", "uzb",
    "kaz", "ben", "tam", "tel", "jav", "lug", "lin", "xho"
]

CODE_TO_NAME = {
    "fra": "Fre", "deu": "Ger", "zho": "Chi", "jpn": "Jap", "nld": "Dut", 
    "ell": "Gre", "ron": "Rom", "nob": "Nor", "swe": "Swe", "dan": "Dan", 
    "isl": "Ice", "fin": "Fin", "bul": "Bul", "pol": "Pol", "rus": "Rus", 
    "spa": "Spa", "por": "Por", "ita": "Ita", "eng": "Eng", "hin": "Hin", 
    "urd": "Urd", "tha": "Tha", "kor": "Kor", "lav": "Lav", "lit": "Lit", 
    "est": "Est", "mlt": "Mlt", "cat": "Cat", "eus": "Bas", "hun": "Hun", 
    "ara": "Ara", "swa": "Swa", "tur": "Tur", "heb": "Heb", "fas": "Pes", 
    "mon": "Mon", "nep": "Nep", "pan": "Pan", "snd": "Snd", "afr": "Afr", 
    "amh": "Amh", "lat": "Lat", "nno": "Nno", "slv": "Slv", "som": "Som", 
    "tgl": "Tgl", "vie": "Vie", "msa": "Msa" 
}

ISO_TO_RGL_FOLDER = {
    "eng": "english", "fra": "french", "deu": "german", "spa": "spanish", 
    "ita": "italian", "swe": "swedish", "por": "portuguese", "rus": "russian", 
    "zho": "chinese", "jpn": "japanese", "ara": "arabic", "hin": "hindi", 
    "fin": "finnish", "est": "estonian", "swa": "swahili", "tur": "turkish", 
    "bul": "bulgarian", "pol": "polish", "ron": "romanian", "nld": "dutch", 
    "dan": "danish", "nob": "norwegian", "isl": "icelandic", "ell": "greek", 
    "heb": "hebrew", "lav": "latvian", "lit": "lithuanian", "mlt": "maltese", 
    "hun": "hungarian", "cat": "catalan", "eus": "basque", "tha": "thai", 
    "urd": "urdu", "fas": "persian", "mon": "mongolian", "nep": "nepali", 
    "pan": "punjabi", "snd": "sindhi", "afr": "afrikaans", "amh": "amharic", 
    "kor": "korean", "lat": "latin", "nno": "nynorsk", "slv": "slovenian", 
    "som": "somali", "tgl": "tagalog", "vie": "vietnamese"
}

ISO_TO_SHARED_LIB = {
    "fra": "romance", "spa": "romance", "ita": "romance", "por": "romance", 
    "ron": "romance", "cat": "romance", "swe": "scandinavian", "dan": "scandinavian", 
    "nob": "scandinavian", "nno": "scandinavian", "fin": "uralic", "est": "uralic"
}

ISO_TO_FACTORY_FOLDER = {
    "zul": "zulu", "yor": "yoruba", "ibo": "igbo", "hau": "hausa", "wol": "wolof", 
    "kin": "kinyarwanda", "kor": "korean", "ind": "indonesian", "msa": "malay", 
    "tgl": "tagalog", "vie": "vietnamese", "que": "quechua", "nav": "navajo", 
    "aym": "aymara", "grn": "guarani", "fry": "frisian", "bre": "breton", 
    "oci": "occitan", "gla": "gaelic", "nah": "nahuatl", "tat": "tatar", 
    "kur": "kurdish", "xho": "xhosa", "lug": "ganda", "lin": "lingala", 
    "som": "somali", "jav": "javanese", "tam": "tamil", "tel": "telugu", 
    "ben": "bengali", "uzb": "uzbek", "kaz": "kazakh"
}

VOCAB_STUBS = {
    "rus": {"n": "животное", "v": ["идти", "иду"]}, 
    "lat": {"n": "animal", "v": ["ambulare", "ambulo"]},
    "default": {"n": "animal", "v": "walk"}
}

GF_DIR = os.path.dirname(os.path.abspath(__file__))
PGF_OUTPUT_FILE = os.path.join(GF_DIR, "Wiki.pgf")
ABSTRACT_NAME = "AbstractWiki"
BUILD_LOGS_DIR = os.path.join(GF_DIR, "build_logs")

# ===========================================================================
# GENERATORS
# ===========================================================================

def get_gf_suffix(iso_code):
    return CODE_TO_NAME.get(iso_code, iso_code.capitalize())

def generate_abstract():
    filename = f"{ABSTRACT_NAME}.gf"
    content = f"""abstract {ABSTRACT_NAME} = {{
  cat Entity; Property; Fact; Predicate; Modifier; Value;
  fun
    mkFact : Entity -> Predicate -> Fact;
    mkIsAProperty : Entity -> Property -> Fact;
    FactWithMod : Fact -> Modifier -> Fact;
    mkLiteral : Value -> Entity;
    Entity2NP : Entity -> Entity; Property2AP : Property -> Property; VP2Predicate : Predicate -> Predicate;
    lex_animal_N : Entity; lex_walk_V : Predicate; lex_blue_A : Property;
}}\n"""
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f: 
        f.write(content)
    return filename

def generate_interface():
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
    suffix = get_gf_suffix(iso_code)
    filename = f"Wiki{suffix}.gf"
    words = VOCAB_STUBS.get(iso_code, VOCAB_STUBS["default"])
    
    v_raw = words['v']
    if isinstance(v_raw, list):
        verb_args = " ".join([f'"{arg}"' for arg in v_raw])
    else:
        verb_args = f'"{v_raw}"'
        
    content = f"""concrete Wiki{suffix} of {ABSTRACT_NAME} = WikiI ** open Syntax{suffix}, Paradigms{suffix}, Symbolic{suffix} in {{
  lin
    lex_animal_N = mkNP (mkN "{words['n']}");
    lex_walk_V = mkVP (mkV {verb_args});
    lex_blue_A = mkAP (mkA "blue"); 
    mkLiteral v = symb v.s;
}};\n"""
    with open(os.path.join(GF_DIR, filename), 'w', encoding='utf-8') as f: 
        f.write(content)
    return filename

# ===========================================================================
# BUILD LOGIC
# ===========================================================================

def get_base_paths():
    rgl_base = os.environ.get("GF_LIB_PATH")
    if not rgl_base:
        for p in ["/usr/local/lib/gf", r"C:\gf-rgl-20250812", r"C:\Program Files\GF\lib"]:
            if os.path.exists(p): rgl_base = p; break
    
    rgl_src_base = None
    if rgl_base and os.path.exists(os.path.join(rgl_base, "src")):
        rgl_src_base = os.path.join(rgl_base, "src")
    elif rgl_base:
        rgl_src_base = rgl_base

    return rgl_src_base

def resolve_language_path(iso_code, rgl_src_base):
    suffix = get_gf_suffix(iso_code)
    target_file = f"Wiki{suffix}.gf"
    
    contrib_base = os.path.join(GF_DIR, "contrib")
    factory_base = os.path.join(GF_DIR, "generated", "src")
    
    paths = [GF_DIR, "."] 

    if rgl_src_base:
        paths.extend([
            rgl_src_base, 
            os.path.join(rgl_src_base, "api"), 
            os.path.join(rgl_src_base, "prelude"), 
            os.path.join(rgl_src_base, "abstract"), 
            os.path.join(rgl_src_base, "common")
        ])

    # 1. Contrib
    contrib_path = os.path.join(contrib_base, iso_code, target_file)
    if os.path.exists(contrib_path):
        paths.append(os.path.dirname(contrib_path))
        return contrib_path, paths

    # 2. Factory
    folder = iso_code.lower() 
    factory_path = os.path.join(factory_base, folder, target_file)
    if os.path.exists(factory_path):
        paths.append(os.path.dirname(factory_path))
        return factory_path, paths
        
    # 3. RGL
    if rgl_src_base:
        rgl_folder = ISO_TO_RGL_FOLDER.get(iso_code)
        if rgl_folder:
            full_rgl_path = os.path.join(rgl_src_base, rgl_folder)
            syntax_file = f"Syntax{suffix}.gf"
            syntax_exists = os.path.exists(os.path.join(full_rgl_path, syntax_file)) or \
                            os.path.exists(os.path.join(rgl_src_base, "api", syntax_file))
            
            if syntax_exists:
                generated_file = os.path.join(GF_DIR, target_file)
                generate_rgl_connector(iso_code)
                paths.append(full_rgl_path)
                shared = ISO_TO_SHARED_LIB.get(iso_code)
                if shared: paths.append(os.path.join(rgl_src_base, shared))
                return generated_file, paths

    return None, None

def main():
    print("🚀 Abstract Wiki Architect: Assembly Line (Logging Mode)")
    
    # 0. Setup Logs Directory
    if os.path.exists(BUILD_LOGS_DIR):
        shutil.rmtree(BUILD_LOGS_DIR)
    os.makedirs(BUILD_LOGS_DIR)
    print(f"[*] Logs initialized at: {BUILD_LOGS_DIR}")

    # 1. Generate & Compile Abstract Grammar FIRST
    print("[-] Compiling AbstractWiki.gf...")
    generate_abstract()
    generate_interface()
    
    abs_path = os.path.join(GF_DIR, "AbstractWiki.gf")
    
    env = os.environ.copy()
    try:
        cmd = ["gf", "-make", "-v", abs_path]
        subprocess.run(cmd, check=True, cwd=GF_DIR, env=env)
        print("✅ AbstractWiki.gfo created.")
    except subprocess.CalledProcessError:
        print("❌ Fatal: Could not compile AbstractWiki.gf")
        sys.exit(1)

    rgl_src_base = get_base_paths()
    valid_files = []
    all_paths = []
    failed_langs = []

    print(f"[*] Inspecting {len(TARGET_LANGUAGES)} languages...")
    
    for iso in TARGET_LANGUAGES:
        file_path, paths = resolve_language_path(iso, rgl_src_base)
        
        if not file_path:
            continue

        if GF_DIR not in paths: paths.insert(0, GF_DIR)
        
        deduped_paths = []
        for p in paths:
            if p not in deduped_paths: deduped_paths.append(p)
        
        path_arg = os.pathsep.join(deduped_paths)
        
        # Compile individual language
        cmd = ["gf", "-make", "-v", "-path", path_arg, file_path]
        
        try:
            result = subprocess.run(
                cmd, 
                cwd=GF_DIR, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                print(f"✅ {iso}: Compiled")
                valid_files.append(file_path)
                for p in deduped_paths: 
                    if p not in all_paths: all_paths.append(p)
            else:
                log_file = os.path.join(BUILD_LOGS_DIR, f"{iso}.log")
                print(f"❌ {iso}: Failed (See {iso}.log)")
                
                # Write individual log file
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write(f"--- COMPILE ERROR FOR {iso} ---\n")
                    f.write(f"COMMAND: {' '.join(cmd)}\n")
                    f.write("-" * 40 + "\n")
                    f.write(result.stderr)
                    f.write(result.stdout)
                
                failed_langs.append(iso)

        except Exception as e:
            print(f"❌ {iso}: Process Error {e}")
            failed_langs.append(iso)

    if failed_langs:
        print(f"\n⚠️  {len(failed_langs)} languages failed. Check {BUILD_LOGS_DIR}/<lang>.log")
    
    if not valid_files:
        print("❌ Critical: No languages compiled successfully.")
        sys.exit(1)

    print(f"\n🔗 Linking {len(valid_files)} valid languages into Wiki.pgf...")
    
    final_paths = list(all_paths)
    if GF_DIR not in final_paths: final_paths.insert(0, GF_DIR)
    
    path_arg = os.pathsep.join(final_paths)
    
    build_cmd = ["gf", "-make", "-path", path_arg, "AbstractWiki.gf"] + valid_files
    
    try:
        subprocess.run(build_cmd, check=True, cwd=GF_DIR, env=env)
        
        generated_pgf = os.path.join(GF_DIR, f"{ABSTRACT_NAME}.pgf")
        if os.path.exists(generated_pgf):
            if os.path.exists(PGF_OUTPUT_FILE):
                os.remove(PGF_OUTPUT_FILE)
            os.rename(generated_pgf, PGF_OUTPUT_FILE)
            print(f"📦 SUCCESS! Binary created at: {PGF_OUTPUT_FILE}")
            print(f"📊 Stats: {len(valid_files)} included, {len(failed_langs)} skipped.")
            
            # FORCE SUCCESS EXIT for Docker so container starts even with partial languages
            sys.exit(0)
        else:
            print("❌ Linker failed: PGF not created.")
            sys.exit(1)
            
    except subprocess.CalledProcessError:
        print("❌ Final linking failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()