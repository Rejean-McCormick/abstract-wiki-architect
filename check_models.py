import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load .env
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ Error: GOOGLE_API_KEY not found.")
    exit(1)

print(f"🔑 Key found: {api_key[:5]}...{api_key[-3:]}")

# Configure
genai.configure(api_key=api_key)

print("\n📡 Connecting to Google API...")
print("-" * 60)
print(f"{'MODEL NAME':<40} | {'METHODS'}")
print("-" * 60)

try:
    count = 0
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"{m.name:<40} | {m.supported_generation_methods}")
            count += 1
    print("-" * 60)
    
    if count == 0:
        print("⚠️  No models found. Check API Key permissions/region.")
    else:
        print(f"✅ Found {count} valid models.")

except Exception as e:
    print(f"\n❌ API Error: {e}")
