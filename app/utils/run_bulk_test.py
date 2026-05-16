import os

from app.utils.intel_processor import analyze_satellite_image

# Create a list of different images you want to test
# Make sure these images are dropped into your folder!
test_images = [
    "/home/alex/Development/projects/hackathon/assets/test/1.png",
    "/home/alex/Development/projects/hackathon/assets/test/2.png",
    "/home/alex/Development/projects/hackathon/assets/test/3.png",
]

print("=== STARTING SYSTEMS BATCH TESTING ===")

for img_file in test_images:
    if not os.path.exists(img_file):
        print(f"⚠️ Skipping '{img_file}' - File not found in directory.")
        continue

    print(f"\n[*] Processing Frame: {img_file}...")

    # Generate a unique output file name for each test
    output_name = f"result_{img_file}"

    # Run our black-box function!
    report = analyze_satellite_image(img_file, output_dir="assets/result")

    # Print out the clean system payload architecture
    if report["status"] == "success":
        print(f"✅ Analysis Complete! Targets found: {report['total_detected']}")
        for item in report["data"]:
            print(
                f"   -> System Log: {item['target_id']} verified at [{item['coordinates']['x']}, {item['coordinates']['y']}]"
            )
        print(f"   Telemetry image compiled: {output_name}")
    else:
        print(f"❌ Error analyzing frame: {report['message']}")

print("\n=== BATCH TESTING COMPLETE ===")
