import os
import json

# Ensure directory exists
os.makedirs("data/samples", exist_ok=True)

# Create a sample biography frame using Italian base lemmas
data = {
    "frame_type": "bio",
    "name": "Marie Curie",
    "gender": "female",
    "profession": "fisico",  # Italian lemma for physicist
    "nationality": "polacco",  # Italian lemma for Polish
}

with open("data/samples/marie_curie_it.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("✅ Created data/samples/marie_curie_it.json")
