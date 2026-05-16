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
    region: str = "Helsinki",
    min_lat: float = Query(None),
    min_lng: float = Query(None),
    max_lat: float = Query(None),
    max_lng: float = Query(None)
):
    bbox_dict = None
    if min_lat and min_lng and max_lat and max_lng:
        bbox_dict = {
            "min_lat": min_lat,
            "min_lng": min_lng,
            "max_lat": max_lat,
            "max_lng": max_lng
        }   
    weather_data = await get_weather_data(region, bbox_dict)
    return {"region": region, "weather_data": weather_data} 
