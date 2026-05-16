import os
import json
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
import math
import requests
from dotenv import load_dotenv

load_dotenv()
MAPTILER_API_KEY = os.getenv("MAPTILER_API_KEY")
NLS_API_KEY = os.getenv("NLS_API_KEY")

def get_region(region_name: str, country_code: str = "fi"):
    url = f"https://api.maptiler.com/geocoding/{region_name}.json"
    params = {
        "key": MAPTILER_API_KEY,
        "country": country_code,
        "types": "region"
    }

	response = requests.get(url, params=params)
	response.raise_for_status()
	features = response.json().get("features", [])
	if not features:
		raise ValueError(f"No region found for '{region_name}'")
	feature = features[0]

    return {
        "name": feature["place_name"],
        "id": feature["id"],
        "center": {
            "lng": feature["center"][0],
            "lat": feature["center"][1]
        },
        "bbox": {
            "min_lng": feature["bbox"][0],
            "min_lat": feature["bbox"][1],
            "max_lng": feature["bbox"][2],
            "max_lat": feature["bbox"][3]
        }
    }

def save_nls_topographic_image(
    bbox: dict,
    zoom : int = 6,
    filename : str = "nls_topographic_image.png"
):
    n = 2 ** zoom
    x_min = int((bbox["min_lng"] + 180) / 360 * n)
    x_max = int((bbox["max_lng"] + 180) / 360 * n)
    y_min = int((1.0 - math.log(math.tan(math.radians(bbox["max_lat"])) + 1 / math.cos(math.radians(bbox["max_lat"]))) / math.pi) / 2.0 * n)
    y_max = int((1.0 - math.log(math.tan(math.radians(bbox["min_lat"])) + 1 / math.cos(math.radians(bbox["min_lat"]))) / math.pi) / 2.0 * n)

    tile_size = 256
    cols = x_max - x_min + 1
    rows = y_max - y_min + 1

    full_image = Image.new("RGB", (cols * tile_size, rows * tile_size))

region = get_region("North Karelia")
save_region_image(region)
save_to_json(region)
