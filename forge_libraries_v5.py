import os
import glob
import re

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
RGL_SRC = "gf-rgl/src"

# MAPPING: Wiki Code (File Name) -> RGL Code (Module Name)
LANG_MAP = {
    "Afr": "Afr", "Amh": "Amh", "Ara": "Ara", "Bul": "Bul", "Cat": "Cat", 
    "Chi": "Chi", "Zho": "Chi", "Dan": "Dan", "Deu": "Ger", "Dut": "Dut", 
    "Eng": "Eng", "Est": "Est", "Fin": "Fin", "Fra": "Fre", "Fre": "Fre", 
    "Ger": "Ger", "Gre": "Gre", "Heb": "Heb", "Hin": "Hin", "Hun": "Hun", 
    "Ice": "Ice", "Ind": "Ind", "Ita": "Ita", "Kor": "Kor", "Lat": "Lat", 
    "Lav": "Lav", "Lit": "Lit", "Mlt": "Mlt", "Mon": "Mon", "Nep": "Nep", 
    "Nno": "Nno", "Nor": "Nor", "Pes": "Pes", "Pol": "Pol", "Por": "Por", 
    "Rus": "Rus", "Slv": "Slo", "Snd": "Snd", "Som": "Som", "Spa": "Spa", 
    "Swa": "Swa", "Swe": "Swe", "Tha": "Tha", "Tur": "Tur", "Urd": "Urd", 
    
    # --- RGL Name/Folder Mismatches (The Fix) ---
    "Bas": "Eus", # WikiBas -> CatEus
    "Jap": "Jpn", # WikiJap -> CatJpn
    "Jpn": "Jpn",
    "Pan": "Pnb", # WikiPan -> CatPnb
    "Rom": "Ron", # WikiRom -> CatRon
}

# The languages we will skip for now due to complexity/known crashes
TARGETS_TO_SKIP_NOW = ["Ara", "Amh", "Heb", "Kor"] 

REQUIRED_LEXICON = [ # Snipped for brevity...
    "animal_N", "bad_A", "bear_N", "big_A", "bird_N", "black_A", "blue_A", 
    "book_N", "boy_N", "bread_N", "buy_V", "car_N", "cat_N", "child_N", 
    "city_N", "clean_A", "cloud_N", "cold_A", "come_V", "computer_N", 
    "cow_N", "dirty_A", "doctor_N", "dog_N", "drink_V", "eat_V", "enemy_N", 
    "fish_N", "flower_N", "fly_V", "friend_N", "fruit_N", "girl_N", "go_V", 
    "good_A", "green_A", "here_Adv", "horse_N", "hot_A", "house_N", "jump_V", 
    "kill_V", "know_V", "language_N", "live_V", "love_V", "man_N", "moon_N", 
    "mountain_N", "music_N", "never_Adv", "new_A", "old_A", "person_N", 
    "play_V", "rain_N", "read_V", "red_A", "river_N", "run_V", "science_N", 
    "sea_N", "see_V", "ship_N", "short_A", "sleep_V", "small_A", "star_N", 
    "stone_N", "sun_N", "swim_V", "teacher_N", "there_Adv", "think_V", 
    "tomorrow_Adv", "train_N", "tree_N", "walk_V", "warm_A", "water_N", 
    "white_A", "woman_N", "write_V", "yellow_A", "young_A"
]

def forge_symbolic(wiki_code, rgl_code):
    filename = os.path.join(GF_DIR, f"Symbolic{wiki_code}.gf")
    content = f"""
resource Symbolic{wiki_code} = open Syntax, Paradigms{rgl_code}, Noun{rgl_code} in {{
  oper
    symb : Str -> NP = \\s -> mkNP (mkPN s) ; 
}}
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

def forge_dictionary(wiki_code, rgl_code):
    filename = os.path.join(GF_DIR, f"Dict{wiki_code}.gf")
    header = f"""
resource Dict{wiki_code} = open Cat{rgl_code}, Paradigms{rgl_code}, Syntax{rgl_code}, Prelude in {{
  oper
    mkAdvS : Str -> Adv = \\s -> lin Adv {{ s = s }} ;
"""
    body = ""
    for key in REQUIRED_LEXICON:
        parts = key.split('_')
        word = parts[0]
        cat = parts[1]
        func_name = f"lex_{key}"
        if cat == "N":
            body += f"    {func_name} = mkN \"{word}\" ;\n"
        elif cat == "A":
            body += f"    {func_name} = mkA \"{word}\" ;\n"
        elif cat == "V":
            body += f"    {func_name} = mkV \"{word}\" ;\n"
        elif cat == "Adv":
            body += f"    {func_name} = mkAdvS \"{word}\" ;\n"
        else:
            body += f"    {func_name} = mkN \"{word}\" ;\n"

    footer = "}\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(header + body + footer)

def run():
    print("🚀 Starting Library Forge VFINAL (RGL Naming Fix)...")
    
    # 1. Clean residual files
    os.system(f"rm {GF_DIR}/*.gfo 2>/dev/null")

    wiki_files = glob.glob(os.path.join(GF_DIR, "Wiki*.gf"))
    
    for file_path in wiki_files:
        wiki_code = os.path.basename(file_path)[4:-3] 
        
        if wiki_code == "I" or len(wiki_code) != 3 or wiki_code in TARGETS_TO_SKIP_NOW: 
             continue
        
        rgl_code = LANG_MAP.get(wiki_code, wiki_code)
        
        print(f"   ⚙️ Processing {wiki_code} -> RGL:{rgl_code}")

        # 1. Forge Symbolic
        forge_symbolic(wiki_code, rgl_code)
        
        # 2. Forge Dictionary
        forge_dictionary(wiki_code, rgl_code)

    print("\n✅ Forge Complete. Ready for compilation.")

if __name__ == "__main__":
    run()