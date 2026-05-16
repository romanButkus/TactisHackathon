import pandas as pd
import os

def calculate_drone_zone(wind_speed, visibility):
    """Returns 1, 2, 3, or None if vital data is missing."""
    # If either critical value is missing, return None (Pandas will show this as NaN)
    if pd.isna(wind_speed) or pd.isna(visibility):
        return None

    # Zone 3: Critical / No-Fly (Heavy wind OR blind conditions)
    if wind_speed > 10 or visibility < 2000:
        return 3
    # Zone 2: Caution / Marginal
    elif (5 <= wind_speed <= 10) or (2000 <= visibility <= 5000):
        return 2
    # Zone 1: Optimal / Safe
    return 1

def analyze_drone_missions(json_file="weather_history.json"):
    if not os.path.exists(json_file):
        print(f"Error: '{json_file}' not found.")
        return

    df = pd.read_json(json_file)
    if df.empty:
        return

    # Calculate drone zone without inventing values
    df["drone_zone"] = df.apply(
        lambda row: calculate_drone_zone(
            row.get("wind_speed"), 
            row.get("visibility")
        ), 
        axis=1
    )

    print("\n================ TACTICAL DRONE ZONE ANALYSIS ================")
    columns_to_show = [col for col in ["wind_speed", "visibility", "rain", "snow", "drone_zone"] if col in df.columns]
    print(df[columns_to_show].to_string(index=False))
    
    print("\n================ ZONE DISTRIBUTION SUMMARY ================")
    # dropna=False ensures that the NaN/Missing count is explicitly shown in the summary
    zone_counts = df["drone_zone"].value_counts(dropna=False).to_dict()
    
    for zone, count in zone_counts.items():
        if pd.isna(zone):
            status = "⚪ UNKNOWN (Missing Data)"
            zone_label = "NaN"
        else:
            zone_label = f"Zone {int(zone)}"
            status = "🟢 Safe" if zone == 1 else "🟡 Caution" if zone == 2 else "🔴 NO-FLY"
            
        print(f"{zone_label} ({status}): {count} location(s)")

if __name__ == "__main__":
    analyze_drone_missions()