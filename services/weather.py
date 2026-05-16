import httpx
import xml.etree.ElementTree as ET
import json
import os
import asyncio
from dotenv import load_dotenv
import httpx

load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

def get_coords_from_regions(region_name: str):
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "..", "regions.json")
    
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
        for r in regions:
            #Check if the searched region is found in the "name" field of the json file
            if region_name.lower() in r["name"].lower():
                lat = r["center"]["lat"]
                lng = r["center"]["lng"]
                return lat, lng

        
    return None, None
#Change get_weather_data to accept lat and lng parameters

async def get_weather_data(region: str = "Helsinki", lat: float = None, lng: float = None):
    url = "https://api.openweathermap.org/data/2.5/weather"
    
    params = {
        "appid": OPENWEATHER_API_KEY,
        "units": "metric"
    }
    #If lat and lng are not provided as parameters, try to find them from regions.json
    
    if lat is None or lng is None:
        r_lat, r_lng = get_coords_from_regions(region)
        if r_lat is not None and r_lng is not None:
            lat, lng = r_lat, r_lng
    # Use give lat and lng if provided
    if lat is not None and lng is not None:
        params["lat"] = lat
        params["lon"] = lng
    else:
        #If no coordinates were provided and couldnt be found from the file, use city name to fetch data
        params["q"] = region

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)

    if response.status_code != 200:
        return {"error": f"Failed to fetch data from OpenWeather: {response.status_code}"}

    data = response.json()
    # Final cordinates are extracted from the OpenWeather response, 
    final_lat = data.get("coord", {}).get("lat", 0.0)
    final_lon = data.get("coord", {}).get("lon", 0.0)
    time_unix = data.get("dt", 0)

    observation = {
        "latitude": final_lat,
        "longitude": final_lon,
        "time": time_unix
    }

    if "main" in data and "temp" in data["main"]:
        observation["t2m"] = data["main"]["temp"]
    if "wind" in data and "speed" in data["wind"]:
        observation["wind_speed"] = data["wind"]["speed"]
    if "wind" in data and "deg" in data["wind"]:
        observation["wind_deg"] = data["wind"]["deg"]
        #visibility in m
    if "visibility" in data:
        observation["visibility"] = data["visibility"]
    if "rain" in data and "1h" in data["rain"]:
        observation["rain"] = data["rain"]["1h"]
    if "snow" in data and "1h" in data["snow"]:
        observation["snow"] = data["snow"]["1h"]

    return observation

async def get_all_regions_weather():
    
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, "..", "regions.json")
        
        if not os.path.exists(json_path):
            return []
            
        with open(json_path, "r", encoding="utf-8") as f:
            regions = json.load(f)
            
        tasks = []
        for r in regions:
            name = r["name"]
            lat = r["center"]["lat"]
            lng = r["center"]["lng"]
            #Search for all regions simultaneously
            tasks.append(get_weather_data(region=name, lat=lat, lng=lng))
            
        weather_results = await asyncio.gather(*tasks)
        
        combined = []
        for r, w in zip(regions, weather_results):
            combined.append({
                "region": r["name"],
                "weather_data": w
            })
        return combined



if __name__ == "__main__":
    tulos = asyncio.run(get_all_regions_weather())
    print(json.dumps(tulos, indent=2))

def save_to_json(data, filename="regions.json"):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    