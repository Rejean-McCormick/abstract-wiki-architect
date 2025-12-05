import os
import json

# Ensure directory exists
os.makedirs("data/samples", exist_ok=True)

# Create a sample biography frame
data = {
    "frame_type": "bio",
    "name": "Marie Curie",
    "gender": "female",
    "profession": "physicist",
    "nationality": "polish",
}

with open("data/samples/marie_curie.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("✅ Created data/samples/marie_curie.json")
