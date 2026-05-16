from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Hackathon API", version="1.0.0")

# Setup CORS so your React frontend can talk to this API for later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Your Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "online", "version": "1.0.0"}


@app.get("/weather")
async def show_weather(
    region: str | None = None,
    lat: float = None,
    lng: float = None
):
    # If empty -> error
    if not region and (lat is None or lng is None):
        return {"error": "Provide a region parameter or coordinates (lat, lng)"}
        
    weather_data = await get_weather_data(region, lat, lng)
    return {"region": region, "weather_data": weather_data}


@app.get("/weather/all")
async def show_all_weather():
    weather_data = await get_all_regions_weather()
    return {"data": weather_data}
