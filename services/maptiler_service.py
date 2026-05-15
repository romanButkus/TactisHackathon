import os
import requests
from dotenv import load_dotenv1

load_dotenv()
API_KEY = os.getenv("MAPTILER_API_KEY")

def get_region(region_name: str, country_code: str = "fi", width: int = 800, height: int = 600, filename: str = "{region_name}.png"):
	url=f"https://api.maptiler.com/geocoding/{region_name}.json"
	params = {
		"key": API_KEY,
		"countrycode": country_code,
		"types": "region"
	}

	response = requests.get(url, params=params)
	response.raise_for_status()
	data = response.json()

	return {
		"name" : feature["region_name"],
		"id" : feature["id"],
		"center" :{
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

def save_region_image(region_name: dict, style: str = "topo-v2", width: int = 800, height: int = 600, filename: str = "{region_name}.png"):
	bbox = region_name["bbox"]
	url = (
		f"https://api.maptiler.com/maps/{style}/static/"
		f"{bbox['min_lng']},{bbox['min_lat']},{bbox['max_lng']},{bbox['max_lat']}/"
		f"{width}x{height}.png"
	)
	response = requests.get(url, params={"key": API_KEY})
	response.raise_for_status()

	#Save the image for certain region
	filename = region_name["name"].split(",")[0].lower().replace(" ", "_") + ".png"
	with open(filename, 'wb') as f:
		f.write(response.content)
	print(f"Saved image for {region_name['name']} as {filename}")
	return filename

def save_to_json(data, filename = "regions.json"):
	with open(filename, 'w') as f:
		json.dump(region_data, f, indent=4)
	print(f"Saved region data to {filename}")

region = get_region("North Karelia")
save_region_image(region)
save_to_json(region)