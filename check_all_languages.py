import requests
import json
import time

API_URL = "http://localhost:8000"

# The test payload (Universal Frame)
TEST_FRAME = {
    "frame_type": "entity.person",
    "name": "TestUser",
    "profession": "Scientist",
    "nationality": "Human"
}

def check_all():
    print(f"🚀 Connecting to Architect API at {API_URL}...")
    
    # 1. Get list of loaded languages
    try:
        info_resp = requests.get(f"{API_URL}/info")
        info_resp.raise_for_status()
        data = info_resp.json()
        languages = data.get("supported_languages", [])
        
        print(f"📋 Found {len(languages)} active languages.")
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Failed to fetch language list: {e}")
        return

    # 2. Test each language
    passed = []
    failed = []

    for i, lang_code in enumerate(languages):
        payload = {
            "lang": lang_code,
            "frame": TEST_FRAME
        }
        
        try:
            start = time.time()
            resp = requests.post(f"{API_URL}/generate", json=payload)
            duration = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                result = resp.json()
                text = result.get("text", "").strip()
                print(f"✅ [{lang_code}] {duration:.0f}ms : {text}")
                passed.append(lang_code)
            else:
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