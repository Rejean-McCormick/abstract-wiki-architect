# build_orchestrator.py
import os
import sys
import subprocess

# Ensure we can import the builder package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from builder import strategist, forge, compiler, healer

def run_scanner():
    """Runs the RGL Scanner to update the Everything Matrix inventory."""
    print("\n--- [1/4] Scanning RGL (Everything Matrix) ---")
    
    # Path to your scanner script
    scanner_script = os.path.join("tools", "everything_matrix", "rgl_scanner.py")
    
    # Fallback: check root if not in tools
    if not os.path.exists(scanner_script):
        scanner_script = "rgl_scanner.py"

    if os.path.exists(scanner_script):
        try:
            subprocess.run(["python", scanner_script], check=True)
            print("   ✅ Inventory updated.")
        except subprocess.CalledProcessError:
            print("   ⚠️  Scanner failed. Proceeding with existing inventory...")
    else:
        print(f"   ⚠️  Scanner script not found at {scanner_script}. Skipping.")

def main():
    print("="*60)
    print("🏛️  ABSTRACT WIKI ARCHITECT - BUILD ORCHESTRATOR (AI-POWERED)")
    print("="*60)
    
    # 1. SCAN (Update the Facts)
    run_scanner()
    
    # 2. STRATEGIZE (The Brain)
    # Reads inventory + strategies.json -> Writes build_plan.json
    print("\n--- [2/4] Calculating Strategy ---")
    success = strategist.generate_plan()
    if not success:
        print("❌ Strategist failed. Aborting.")
        sys.exit(1)
    
    # 3. FORGE (The Hands)
    # Reads build_plan.json -> Writes .gf files
    print("\n--- [3/4] Forging Code ---")
    forge.run()
    
    # 4. COMPILE & HEAL (The Muscle + The Surgeon)
    print("\n--- [4/4] Compiling (Pass 1) ---")
    success = compiler.run()
    
    # --- SELF-HEALING LOOP ---
    # We run the healer regardless of success/fail, because "success" 
    # just means the PGF was built, not that all languages passed.
    print("\n🚑 Analyzing Failures for AI Repair...")
    patched = healer.run_healing_round()
    
    if patched:
        print("\n🔄 Updates Applied. Compiling (Pass 2)...")
        success = compiler.run()
    else:
        print("   (No AI repairs needed or possible)")

    print("-" * 60)
    
    if success:
        print("🎉 Orchestration Complete. System Ready.")
    else:
        print("⚠️  Orchestration finished with errors (Partial Build).")
        # Exit 1 only if we failed to produce ANY PGF
        if not os.path.exists(os.path.join("gf", "Wiki.pgf")):
            sys.exit(1)

if __name__ == "__main__":
    main()