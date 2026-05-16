import os
import json
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from attitude_service import get_elevations
import math
import requests

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
    feature = response.json()["features"][0]

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

    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            url = (
                f"https://avoin-karttakuva.maanmittauslaitos.fi/avoin/wmts/1.0.0/"
                f"maastokartta/default/WGS84_Pseudo-Mercator/{zoom}/{y}/{x}.png"
                f"?api-key={NLS_API_KEY}"
            )
            response = requests.get(url)
            if response.status_code == 200:
                tile = Image.open(BytesIO(response.content))
                px = (x - x_min) * tile_size
                py = (y - y_min) * tile_size
                full_image.paste(tile, (px, py))
                print(f"Fetched tile: zoom={zoom}, x={x}, y={y}")
    
    full_image.save(filename)
    print(f"Saved full region image to: {filename}")
    return filename

def save_to_json(data, filename="regions.json"):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Saved: {filename}")

# Fetch al regions
region_names = [
    ("North Karelia", 7),
    ("Varsinais-Suomi", 7),
]

def get_kasivarsi():
    return {
        "name": "Käsivarsi, Lapland",
        "id": "custom_kasivarsi",
        "center": {"lng": 22.5, "lat": 68.8},
        "bbox": {
            "min_lng": 20.5,
            "min_lat": 67.8,
            "max_lng": 24.5,
            "max_lat": 69.8
        }
    }

regions = []

for name, zoom in region_names:
    print(f"Fetching region: {name}")
    region = get_region(name)
    region["elevation"] = get_elevations(region["bbox"])
    region["image"] = save_nls_topographic_image(
            bbox=region["bbox"],
            zoom=zoom,
            filename=f"{name.replace(' ', '_').lower()}_topo.png"
    )
    regions.append(region)

# Käsivarsi separately
kasivarsi = get_kasivarsi()
kasivarsi["elevation"] = get_elevations(kasivarsi["bbox"])
kasivarsi["image"] = save_nls_topographic_image(
    bbox=kasivarsi["bbox"],
    zoom=7,
    filename="kasivarsi_topo.png"
)
regions.append(kasivarsi)

save_to_json(regions)