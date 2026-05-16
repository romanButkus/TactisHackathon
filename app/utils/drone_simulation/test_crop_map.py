import os

from app.utils.drone_simulation.crop_map import generate_tactical_simulation
from app.utils.drone_simulation.intel_processor import analyze_satellite_image

# Operational Configs
MASTER_MAP = "/home/alex/Development/projects/hackathon/assets/test_map.png"
GRID_SIZE = 10
TOTAL_TARGETS = 15

print("=== 🧪 RUNNING MODULAR MATRIX CROP SYSTEM TEST ===")

if not os.path.exists(MASTER_MAP):
    print(f"❌ Aborting: Ensure you have your 4K upscaled image at '{MASTER_MAP}'")
    exit(1)

# Step 1: Fire the upgraded grid generator
target_registry = generate_tactical_simulation(
    MASTER_MAP, grid_size=GRID_SIZE, total_targets=TOTAL_TARGETS
)

# Step 2: Extract which sector file got a target injected into it
sample_target = target_registry[0]
target_sector_id = sample_target["assigned_sector"]
target_file_path = f"assets/test/{target_sector_id}.png"

print(f"\n📡 Selecting Active Sector Target file: {target_file_path}")

# Step 3: Run the completely isolated modular intelligence script
manifest = analyze_satellite_image(target_file_path, output_dir="assets/result")

if manifest["status"] == "success" and manifest["total_detected"] > 0:
    print(f"\n🎯 Targets Detected Successfully in Sector Frame!")

    print(f"💾 Check file path -> 'assets/result/{target_sector_id}_manifest.json'")
    print(f"📸 Check file path -> 'assets/result/{target_sector_id}_target_1.png'")

    print("\n📦 Verified Sample Intel Object Data Matrix:")
    first_item = manifest["data"][0]

    # SYSTEM SAFETY HOOKS: Defensively extract keys to avoid KeyError breaks
    t_id = first_item.get("target_id", "STRUCTURE-01")
    crop_asset = first_item.get("crop_asset_path", "No Asset Generated")

    coords = first_item.get("relative_coordinates", {})
    pct_x = coords.get("percentage_x", 0.0)
    pct_y = coords.get("percentage_y", 0.0)

    print(f"   -> ID: {t_id}")
    print(f"   -> Image Crop Saved to: {crop_asset}")
    print(f"   -> Frame Relative Spot: {pct_x}% X / {pct_y}% Y")
else:
    print("\n❌ Pipeline scan returned 0 detections.")
    print(
        "💡 Debug Tip: The image file was saved, but the color threshold mask found 0 pixels."
    )
    print("   Print the full manifest output here to inspect the base report array:")
    print(json.dumps(manifest, indent=2))

print("\n=== ISOLATED MODULAR ENGINE TEST RUN CONCLUDED ===")
