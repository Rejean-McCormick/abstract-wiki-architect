# check_all_languages.py
import requests
import json
import time

API_URL = "http://localhost:8000"

# [UPDATE] Aligned with app.core.domain.models.Frame structure (V2)
TEST_FRAME = {
    "frame_type": "bio",
    "subject": {
        "name": "Marie Curie",
        "qid": "Q7186"
    },
    "properties": {
        "profession": "physicist",
        "nationality": "polish"
    }
}

def check_all():
    print(f"🚀 Connecting to Architect API at {API_URL}...")
    
    languages = []
    
    # 1. Get list of loaded languages
    try:
        # Try to fetch dynamically from API
        info_resp = requests.get(f"{API_URL}/info")
        if info_resp.status_code == 200:
            data = info_resp.json()
            languages = data.get("supported_languages", [])
            print(f"📋 Retrieved {len(languages)} languages from API.")
    except Exception:
        pass

    # Fallback if API discovery fails (or isn't implemented yet)
    if not languages:
        print("⚠️  Could not auto-discover languages. Using V2 defaults.")
        languages = ["eng", "fra", "deu", "ita", "spa"]

    print("-" * 60)

    # 2. Test each language
    passed = []
    failed = []

    for lang_code in languages:
        try:
            start = time.time()
            
            # [UPDATE] API V2 uses RESTful path: /generate/{lang_code}
            # Payload is now just the frame, not wrapped in a logic envelope
            resp = requests.post(
                f"{API_URL}/generate/{lang_code}", 
                json=TEST_FRAME
            )
            
            duration = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                result = resp.json()
                text = result.get("text", "").strip()
                print(f"✅ [{lang_code}] {duration:.0f}ms : {text}")
                passed.append(lang_code)
            else:
                # Print error details (useful for 422 Validation Errors)
                print(f"❌ [{lang_code}] {resp.status_code} : {resp.text}")
                failed.append(lang_code)
                
        except Exception as e:
            print(f"❌ [{lang_code}] Connection Error : {e}")
            failed.append(lang_code)

    # 3. Summary
    print("-" * 60)
    print(f"🎉 PASSED: {len(passed)}")
    print(f"⚠️  FAILED: {len(failed)}")
    
    if failed:
        print(f"Failed languages: {', '.join(failed)}")

if __name__ == "__main__":
    check_all()