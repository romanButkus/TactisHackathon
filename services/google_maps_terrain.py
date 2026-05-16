import os
import json
import math
import requests
from PIL import Image
from io import BytesIO

def load_regions():
	with open("regions.json", "r") as f:
		return json.load(f)
	
def save_to_json(data, filename = "regions.json"):
	with open(filename, "w") as f:
		json.dump(data, f, indent = 4)
	print(f"Saved to {filename}")

def save_terrain_image(bbox: dict,
											 zoom: int = 9,
											 filename: str = "terrain.png"):
	n = 2 ** zoom

	x_min = int((bbox["min_lng"] + 180) / 360 * n)
	x_max = int((bbox["max_lng"] + 180) / 360 * n)
	y_min = int((1 - math.log(math.tan(math.radians(bbox["max_lat"])) + 1 / math.cos(math.radians(bbox["max_lat"]))) / math.pi) / 2 * n)
	y_max = int((1 - math.log(math.tan(math.radians(bbox["min_lat"])) + 1 / math.cos(math.radians(bbox["min_lat"]))) / math.pi) / 2 * n)

	tile_size = 256
	cols = x_max - x_min + 1
	rows = y_max - y_min + 1

	print(f"Fetching {cols * rows} tiles...")
	full_image = Image.new("RGB", (cols * tile_size, rows * tile_size))

	header = {"User-Agent": "TACTIS/1.0 HackathonProject"}

	for x in range(x_min, x_max + 1):
		for y in range(y_min, y_max + 1):
			url = f"https://tile.opentopomap.org/{zoom}/{x}/{y}.png"

			response = requests.get(url, headers = header)
			if response.status_code == 200:
				tile = Image.open(BytesIO(response.content))
				px = (x - x_min) * tile_size
				py = (y - y_min) * tile_size
				full_image.paste(tile, (px, py))
				print(f"Tile x = {x}, y = {y} fetched successfully.")
			else:
				print(f"Failed to fetch tile x = {x}, y = {y}. Status code: {response.status_code}")
	
	full_image.save(filename)
	print(f"Saved terrain image to {filename}")
	return filename

if __name__ == "__main__":
	regions = load_regions()
	if isinstance(regions, dict):
		regions = [regions]

	zoom_level = {
		"north_karelia" : 9,
		"varsinais_suomi" : 9,
		"käsivarsi" : 9,
	}

	os.makedirs("assets/terrains", exist_ok=True)

	for region in regions:
		name = region["name"].split(",")[0]
		name_key = name.lower().replace(" ", "_")
		zoom = zoom_level.get(name_key, 9)

		print(f"Processing region: {name} with zoom level {zoom}")
		region["terrain_image"] = save_terrain_image(
			bbox = region["bbox"],
			zoom = zoom,
			filename = f"assets/terrains/{name_key}_terrain.png"
		)

	save_to_json(regions)
	print("All regions processed and saved.")