import os
import json
import subprocess
import re
import sys

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
RGL_SRC = "gf-rgl/src"
RGL_PATHS_FILE = "rgl_paths.json"

def run():
    print("🚀 Starting RGL Path Mapping Generation (WSL/Linux Execution)...")
    
    # We must ensure the GF directory is accessible in the Linux command
    wsl_dir = os.getcwd().replace('C:', '/mnt/c').replace('\\', '/')
    
    # Command: Execute 'find' using the WSL bash environment
    # Note: Using '-o -name' must be protected from the shell expansion by single quotes.
    find_cmd = f'find {wsl_dir}/{RGL_SRC} -type f \( -name "Cat*.gf" -o -name "Noun*.gf" \)'

    # We call bash/wsl directly to ensure the command is interpreted correctly
    try:
        result = subprocess.run(
            ['wsl', 'bash', '-c', find_cmd], 
            capture_output=True, 
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running find command: Check if WSL is running or if the path is correct.")
        print(e.stderr)
        return
    except FileNotFoundError:
        print("❌ Error: 'wsl' command not found. Ensure you are running Windows 10/11 with WSL installed.")
        return

    file_list = result.stdout.strip().splitlines()
    path_map = {}
    
    # 2. Process the list and generate the map
    # The output paths will be Linux paths (e.g., /mnt/c/.../afrikaans/CatAfr.gf)
    
    # Determine the prefix to strip (everything up to the language folder)
    prefix_to_strip = f"{wsl_dir}/{RGL_SRC}/"
    
    for full_path in file_list:
        if full_path.startswith(prefix_to_strip):
            relative_path = full_path.replace(prefix_to_strip, "")
            
            # Extract the module name (e.g., CatAfr.gf)
            module_name_match = re.search(r'(Cat[A-Z][a-z]{2}\.gf|Noun[A-Z][a-z]{2}\.gf)', relative_path)
            
            if module_name_match:
                module_name = module_name_match.group(0).replace('.gf', '') # CatAfr
                path_map[module_name] = relative_path
        
    # 3. Save the map to JSON (Windows output)
    with open(RGL_PATHS_FILE, "w") as f:
        json.dump(path_map, f, indent=4)
    
    print(f"\n✅ Created {RGL_PATHS_FILE} with {len(path_map)} definitive file paths.")

if __name__ == "__main__":
    run()