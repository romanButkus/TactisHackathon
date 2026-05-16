import os
import json
import time
from datetime import datetime

STATE_FILE = "live_map_state.json"

def update_live_state(lat, lng, photo_path):
	# === Load existing state ===
	if os.path.exists(STATE_FILE):
		with open(STATE_FILE, "r") as f:
			try:
				state_data = json.load(f)
			except json.JSONDecodeError:
				state_data = {"markers": []}
	else:
		state_data = {"markers": []}

	# === Check if a marker already exists at this location ===
	match_found = False
	for marker in state_data["markers"]:
		if round(marker["lat"], 5) == round(lat, 5) and round(marker["lng"], 5) == round(lng, 5):
			# === Update the photo path and timestamp ===
			marker["photo"] = photo_path
			marker["last_updated"] = datetime.now().isoformat()
			match_found = True
			print(f"Location match found. Overwriting photo at ({lat}, {lng})")
			break

	# === If no match found, add a new marker ===
	if not match_found:
		new_marker = {
			"lat": lat,
			"lng": lng,
			"photo": photo_path,
			"last_updated": datetime.now().isoformat()
		}
		state_data["markers"].append(new_marker)
		print(f"Added new marker at ({lat}, {lng})")

	# === Save updated state back to file ==
	with open(STATE_FILE, "w") as f:
		json.dump(state_data, f, indent=4)

# === Simulated 20 seconds loop ===
drone_ticks = [
	{"lat": 60.192059, "lng": 24.945831, "photo": "/assets/images/north_karelia_topo.png"},
	{"lat": 60.192500, "lng": 24.946000, "photo": "/assets/images/kasivarsi_topo.png"},
	{"lat": 60.192100, "lng": 24.945500, "photo": "/assets/images/varsinais-suomi_topo.png"},
]

for tick in drone_ticks:
    update_live_state(tick["lat"], tick["lng"], tick["photo"])
    print("Waiting 20 seconds for next tick...")
    time.sleep(20)