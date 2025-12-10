import os
import glob

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"

REQUIRED_LEXICON = [
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

def forge_symbolic(lang_code):
    filename = os.path.join(GF_DIR, f"Symbolic{lang_code}.gf")
    print(f"   🔨 Forging Symbolic{lang_code}.gf...")
    
    # Safe Symbolic using Paradigms.mkPN
    content = f"""
resource Symbolic{lang_code} = open Syntax{lang_code}, Paradigms{lang_code} in {{
  oper
    symb : Str -> NP = \\s -> mkNP (mkPN s) ; 
}}
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

def forge_dictionary(lang_code):
    filename = os.path.join(GF_DIR, f"Dict{lang_code}.gf")
    print(f"   🔨 Forging Dict{lang_code}.gf...")

    # HEADER:
    # 1. Open 'Prelude' for 'ss'
    # 2. Define mkAdvS manually to force strings into Adverbs.
    #    (We assume Adv = {s : Str} which is true for 95% of RGL)
    header = f"""
resource Dict{lang_code} = open Cat{lang_code}, Paradigms{lang_code}, Syntax{lang_code}, Prelude in {{
  oper
    -- Force String to Adverb (bypassing strict Paradigms)
    mkAdvS : Str -> Adv = \\s -> lin Adv (ss s) ;
"""
    body = ""
    for key in REQUIRED_LEXICON:
        parts = key.split('_')
        word = parts[0]
        cat = parts[1]
        func_name = f"lex_{key}"
        
        # Use Standard mkN/mkA/mkV (Trust the RGL to handle gender/morphology)
        # Use Custom mkAdvS for Adverbs
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
    print("🚀 Starting Library Forge V3 (Standard+Helper)...")
    
    wiki_files = glob.glob(os.path.join(GF_DIR, "Wiki*.gf"))
    wiki_files += glob.glob(os.path.join(GF_DIR, "Wiki*.gf.SKIP"))
    
    for file_path in wiki_files:
        filename = os.path.basename(file_path)
        if "Wiki.gf" in filename and len(filename) < 10: continue
        
        clean_name = filename.replace(".SKIP", "").replace("Wiki", "").replace(".gf", "")
        if len(clean_name) != 3: continue 
        
        lang_code = clean_name
        
        # Forge
        forge_symbolic(lang_code)
        forge_dictionary(lang_code)
        
        # Restore
        if file_path.endswith(".SKIP"):
            new_path = file_path.replace(".SKIP", "")
            os.rename(file_path, new_path)
            print(f"   ✨ Restored {clean_name}")

    print("\n✅ Forge Complete.")

if __name__ == "__main__":
    run()