import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.gemini import ask_gemini


def clean_json_string(raw_string: str) -> str:
    cleaned = raw_string.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def run_comprehensive_regional_analysis(
    region_data: dict, weather_metadata: dict, detected_objects: list
):
    region_name = region_data["name"]
    bbox = region_data["bbox"]
    elevations = region_data.get("elevation", [])

    # === Prompt 1: Weather ===
    weather_prompt = f"""
  Analyze the following macro weather conditions for the region of {region_name} for military pourposes. Consider how these conditions would affect drone flight operations, including takeoff, navigation, and landing.:
    - Data: {json.dumps(weather_metadata)}
    
    Return a valid JSON object ONLY. Do not wrap it in markdown code blocks.
    Structure: {{
        "severity": "Low/Medium/High",
        "impact_statement": "1 short sentence explaining how this weather affects drone flight."
    }}
  """
    print(f"Executing Weather Analysis Prompt for {region_name}...")
    weather_analysis = ask_gemini(weather_prompt)

    # === Prompt 2: Objects ===
    objects_prompt = f"""
    Analyze these objects and features detected by drones across {region_name} for military purposes. (BBox: {json.dumps(bbox)}):
    - Detected Features List: {json.dumps(detected_objects)}
    
    Identify any tactical patterns or operational obstacles.
    Return a valid JSON object ONLY. Do not wrap it in markdown code blocks.
    Structure: {{
        "hazard_level": "Safe/Caution/Hazardous",
        "object_summary": "1 short sentence describing the distribution of these objects in the region."
    }}
    """
    print(f"Executing Object Analysis Prompt for {region_name}...")
    objects_analysis = ask_gemini(objects_prompt)

    # === Prompt 3: Elevation ===
    elevation_prompt = f"""
    Analyze this geographic elevation matrix sampled across {region_name} fro military purposes. (BBox: {json.dumps(bbox)}):
    - Elevation Points (meters): {json.dumps(elevations)}
    
    Evaluate the terrain roughness and slope characteristics.
    Return a valid JSON object ONLY. Do not wrap it in markdown code blocks.
    Structure: {{
        "terrain_type": "e.g., Flat Lowlands, Undulating Highlands, Rugged Peaks",
        "elevation_summary": "1 short sentence explaining the topographic constraints of this terrain."
    }}
    """
    print(f"Executing Elevation Analysis Prompt for {region_name}...")
    elevation_analysis = ask_gemini(elevation_prompt)

    # === Prompt4: Master and Summary ===
    master_prompt = f"""
    You are the Chief Drone Mission Commander. Synthesize the following sub-analyses for {region_name} into a final operational directive:
    
    [WEATHER INSIGHTS]
    {weather_analysis}
    
    [OBJECT DETECTION INSIGHTS]
    {objects_analysis}
    
    [TOPOGRAPHY INSIGHTS]
    {elevation_analysis}
    
    Evaluate these layers together. Provide a final overall risk assessment and an actionable mission recommendation.
    Return a valid JSON object ONLY. Do not wrap it in markdown code blocks.
    Structure: {{
        "overall_risk_score": "1 to 10 (10 being most dangerous)",
        "integrated_summary": "A 2-sentence synthesis of how weather, objects, and elevations interact here.",
        "flight_recommendation": "A explicit operational recommendation (e.g., 'Proceed with Flight', 'Restricted Altitude Flight Only', or 'No-Fly Order')."
    }}
    """
    print(f"Executing Master Synthesis Prompt for {region_name}...")
    master_analysis = ask_gemini(master_prompt)

    # === Step 2: Parse and package everything for the Frontend ===
    try:
        weather_json = json.loads(clean_json_string(weather_analysis))
        objects_json = json.loads(clean_json_string(objects_analysis))
        elevation_json = json.loads(clean_json_string(elevation_analysis))
        master_json = json.loads(clean_json_string(master_analysis))
    except Exception:
        print(
            f"⚠️ Warning: One of the Gemini JSON payloads for {region_name} failed to parse. Using fallbacks."
        )
        weather_json = {
            "severity": "Unknown",
            "impact_statement": "Weather analysis failed.",
        }
        objects_json = {
            "hazard_level": "Unknown",
            "object_summary": "Object analysis failed.",
        }
        elevation_json = {
            "terrain_type": "Unknown",
            "elevation_summary": "Elevation analysis failed.",
        }
        master_json = {
            "overall_risk_score": "5",
            "integrated_summary": "Analysis completed with partial telemetry.",
            "flight_recommendation": "Hold Flight Operations",
        }

    # === Final payload for this single region ===
    final_payload = {
        "region_name": region_name,
        "base_map": region_data["image"]["filename"],
        "bbox": bbox,
        "modules": {
            "weather": weather_json,
            "objects": objects_json,
            "elevation": elevation_json,
        },
        "master_analysis": master_json,
        "analysis_timestamp": datetime.now().isoformat(),
    }

    print(f"Comprehensive analysis for {region_name} completed.")
    return final_payload  # Changed from file-write to return payload data


if __name__ == "__main__":
    # === Load all region data from regions.json
    with open("regions.json", "r") as f:
        all_regions = json.load(f)

    with open("weather_results.json", "r") as f:
        all_weather = json.load(f)

    with open("assets/result/all_ticks_manifest.json", "r") as f:
        all_objects = json.load(f)

    # Master dictionary to hold data for ALL regions
    master_map_state = {}

    # Loop through every single region in your json array
    for region in all_regions:
        name_key = region["name"]
        print(f"\n--- Processing Region: {name_key} ---")

        # Run the analysis for this single region
        analysis_result = run_comprehensive_regional_analysis(
            region_data=region,
            weather_metadata=all_weather,
            detected_objects=all_objects,
        )

        # Store it inside our master dictionary using the region name as the key
        master_map_state[name_key] = analysis_result

    # === Save the complete multi-region dataset at the end ===
    with open("live_map_state.json", "w") as f:
        json.dump(master_map_state, f, indent=4)

    print(
        "\n✅ All regions analyzed successfully and combined into live_map_state.json!"
    )