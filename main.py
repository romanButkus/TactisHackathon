from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from services.weather import get_all_regions_weather, get_weather_data
from services.attitude_service import get_elevations
import json
import os

app = FastAPI(title="Hackathon Backend", version="1.0.0")

# === Core ===
app.add_middleware(
		CORSMiddleware,
		allow_origins=["*"],  # Vite dev server
		allow_methods=["*"],
		allow_headers=["*"],
)

os.makedirs("assets", exist_ok=True)
app.mount("/static", StaticFiles(directory="assets"), name="static")

# === Loading data from JSON ===
def load_regions_json() -> list:
	with open("regions.json", "r") as f:
		return json.load(f)
	
# === In-memory stores ===
drone_store: dict[str, dict] = {}
object_store: dict[str, dict] = {}

@app.get("/api/regions")
def get_regions():
	raw = load_regions_json()
	
	if isinstance(raw, dict):
		raw = [raw]

	result = []
	colors = ["#4ade80", "#34d399", "#86efac"]

	for i, r in enumerate(raw):
		name = r.get("name", "Unknown")
		name_key = name.lower().replace(" ", "_")
		
		# Extract the actual filename from regions.json
		img_path = r.get("image", {}).get("filename", "")
		img_filename = img_path.replace("\\", "/").split("/")[-1]

		result.append({
			"id" : r.get("id", name_key),
			"name": name.split(",")[0],
			"color" : colors[i % len(colors)],
			"image_url": f"/static/images/{img_filename}",
			"bbox": [
				[r["bbox"]["min_lat"], r["bbox"]["min_lng"]],
				[r["bbox"]["max_lat"], r["bbox"]["max_lng"]]
			],
			"center" : [r["center"]["lat"], r["center"]["lng"]],
			"elevation": {
				"min": round(r.get("elevation", {}).get("min_elevation", 0)),
				"max": round(r.get("elevation", {}).get("max_elevation", 0)),
				"avg": round(r.get("elevation", {}).get("avg_elevation", 0))
			}
		})
	return JSONResponse(content=result)

# === Weather ===
@app.get("/api/weather/all")
async def get_weather_all():
	data = await get_all_regions_weather()
	return JSONResponse(data)
	
@app.get("/api/weather")
async def get_weather(region: str = Query(None), lat: float = Query(None), lng: float = Query(None)):
	data = await get_weather_data(region = region, lat = lat, lng = lng)
	return JSONResponse(data)

# === Elevation ===
@app.get("/api/elevation")
def get_elevation(region: str = Query(...)):
	raw = load_regions_json()
	if isinstance(raw, dict):
		raw = [raw]
	region_data = next(
		(r for r in raw if region.lower() in r["name"].lower()),
		None
	)

	if not region_data:
		return JSONResponse(content={"error": "Region not found"}, status_code=404)
	
	elevations = get_elevations(region_data["bbox"])
	return JSONResponse(elevations)

@app.get("/api/elevation/all")
def get_elevation_all():
	raw = load_regions_json()
	if isinstance(raw, dict):
		raw = [raw]
	
	result = []
	for r in raw:
		elevations = get_elevations(r["bbox"])
		result.append({
			"region" : r["name"],
			"elevation" : elevations
		})
	return JSONResponse(result)

# === Drones ===
@app.get("/api/drones")
def add_drone(data: dict):
	region = data.get("region")
	if not region:
		return JSONResponse(content={"error": "Region is required"}, status_code=400)
	if region not in drone_store:
		drone_store[region] = []

	drone_store[region].append(data)
	return JSONResponse(content={"ok": True})

# === Objects ===
@app.get("/api/objects")
def add_object(data: dict):
	region = data.get("region")
	if not region:
		return JSONResponse(content={"error": "Region is required"}, status_code=400)
	if region not in object_store:
		object_store[region] = []

	object_store[region].append(data)
	return JSONResponse(content={"ok": True})

@app.delete("/api/objects")
def get_intel(region: str = Query(...)):
	drones = drone_store.get(region, [])
	objects = object_store.get(region, [])
	enemies = [o for o in objects if o.get("type") == "enemy"]

	return JSONResponse({
		"sorties" : len(drones),
		"analyzed" : len([d for d in drones if d.get("status") == "analyzed"]),
		"pending" : len([d for d in drones if d.get("status") == "pending"]),
		"enemy_assessment" : {
			"Logistics" : "EXPOSED" if any(o["type"] == "log" for o in enemies) else "UNKNOWN",
			"Air defense" : "UNKNOWN",
			"Mobility" : "LIMITED" if enemies else "UNKNOWN",
			"Supply line" : "ACTIVE" if enemies else "UNKNOWN"
		}
	})

# === Analysis === (Beta)
@app.get("/api/analysis")
def get_analysis(region: str = Query(...)):
    objects = object_store.get(region, [])
    drones  = drone_store.get(region, [])
    enemies = [o for o in objects if o.get("category") == "enemy"]
    high    = [e for e in enemies if e.get("threat") == "HIGH"]

    intel_score  = min(len(drones) * 20, 100)
    strike_score = min(len(high)   * 25, 100)

    if strike_score > 65:
        rec, rec_type = "STRIKE VIABLE — High-value targets confirmed.", "warn"
    elif strike_score > 30:
        rec, rec_type = "CONDITIONS PARTIAL — Gather more intel before strike.", "warn"
    else:
        rec, rec_type = "INSUFFICIENT DATA — Continue ISR operations.", "nogo"

    return JSONResponse({
        "strike"       : strike_score,
        "visibility"   : 50,  # connect to weather
        "accessibility": 50,  # connect to terrain
        "intel"        : intel_score,
        "rec"          : rec,
        "recType"      : rec_type,
    })