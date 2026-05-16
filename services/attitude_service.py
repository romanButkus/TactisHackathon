import time
import requests

def get_elevations(bbox: dict, samples: int = 10):
	locations = []

	for i in range(samples):
		for j in range(samples):
			lat = bbox["min_lat"] + (bbox["max_lat"] - bbox["min_lat"]) * i / (samples - 1)
			lng = bbox["min_lng"] + (bbox["max_lng"] - bbox["min_lng"]) * j / (samples - 1)
			locations.append(f"{lat},{lng}")

	url = "https://api.opentopodata.org/v1/eudem25m"
	params = {"locations": "|".join(locations)}

	time.sleep(1)  # To avoid hitting rate limits
	response = requests.get(url, params=params)	
	response.raise_for_status()
	data = response.json()

	elevations = [r["elevation"] for r in data["results"] if r["elevation"] is not None]

	return {
		"min_elevation": min(elevations) if elevations else None,
		"max_elevation": max(elevations) if elevations else None,
		"avg_elevation": sum(elevations) / len(elevations) if elevations else None
	}