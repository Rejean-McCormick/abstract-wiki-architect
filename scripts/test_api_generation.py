import requests
import json

# Correct URL from previous step
API_URL = "http://localhost:8000/generate"

def test_generation(lang, name, prof, nat):
    print(f"\n--- Testing {lang.upper()} ---")
    
    # 1. Build the inner Frame object
    frame_data = {
        "frame_type": "bio",
        "name": name,
        "profession": prof,
        "nationality": nat
    }
    
    # 2. Build the outer Request Wrapper (Required by API)
    payload = {
        "lang": lang,
        "frame": frame_data,
        "options": { "style": "default" } # Optional, but good practice
    }
    
    try:
        # Note: No 'params' argument. Everything goes in 'json'.
        response = requests.post(API_URL, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ SUCCESS: {data.get('result', 'No text returned')}")
            # Metadata might be nested in 'meta' or 'debug_info' depending on API version
            meta = data.get('meta') or data.get('debug_info') or {}
            print(f"   (Engine: {meta.get('engine', 'Unknown')})")
        else:
            print(f"❌ FAILED ({response.status_code}): {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ FAILED: Could not connect to backend. Is uvicorn running?")

if __name__ == "__main__":
    # 1. French (Expected: Correct sentence)
    test_generation("fr", "Marie Curie", "physicien", "polonais")
    
    # 2. Korean (Expected: "Stub" behavior - likely English fallback or empty string)
    test_generation("ko", "Marie Curie", "physicist", "polish")