import sys
import os

print("--- Abstract Wiki Diagnostic Tool (v3) ---")

try:
    import pgf
except ImportError as e:
    print(f"[FAIL] Could not import 'pgf'. Error: {e}")
    sys.exit(1)

try:
    sys.path.append(os.getcwd())
    from app.shared.config import settings
    real_path = settings.AW_PGF_PATH
    print(f"[INFO] Configured Path: {real_path}")
except Exception as e:
    print(f"[FAIL] Could not load settings: {e}")
    sys.exit(1)

if not os.path.exists(real_path):
    print(f"[FAIL] File NOT found at: {real_path}")
    sys.exit(1)

print(f"[PASS] Found grammar file ({os.path.getsize(real_path)} bytes).")

try:
    gr = pgf.readPGF(real_path)
    print("[PASS] PGF loaded successfully!")
    
    # FIX: gr.languages is a dict, but gr.functions might be a list in your version
    langs = list(gr.languages.keys())
    print(f"\n[DATA] Available Languages: {langs}")
    
    # FIX: Direct access (removed .keys())
    funcs = gr.functions
    print(f"\n[DATA] Abstract Functions (First 20):")
    print(f"       {funcs[:20]}") 

except Exception as e:
    print(f"[FAIL] PGF Error: {e}")