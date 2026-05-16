import json
import os

import cv2
import numpy as np


def classify_object_contour(contour) -> str:
    """
    INTELLIGENCE CLASSIFIER ENGINE:
    Calculates polygon corner counts to map targets to structural types.
    """
    # Smooth and approximate the perimeter chain loop geometry
    perimeter = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
    corners = len(approx)

    # Map geometric profiles back to tactical asset fields
    if corners == 3:
        return "AMMO_DEPOT"  # 3 Sides = Triangle
    elif corners == 4:
        # Check aspect ratio or rotation variance to safely catch squares and diamonds
        _, _, w, h = cv2.boundingRect(contour)
        aspect_ratio = float(w) / h
        # If it's roughly square but has a specific shape profile, check structural bounds
        if 0.85 <= aspect_ratio <= 1.15:
            return "COMMS_CENTER"  # Clean block square
        return "TROOP_FORMATION"  # Diamond/Rhombus stretch profile
    else:
        # Fallback handling in case of anti-aliasing edge rounding distortions
        return "TROOP_FORMATION" if corners > 4 else "AMMO_DEPOT"


def extract_combined_target_contours(img: np.ndarray) -> list:
    """
    Extracts all colorful target signatures by masking away background space.
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Comprehensive color envelope filtering out background noise layers
    # This range grabs red, orange, pink, and violet colors cleanly
    lower_bound = np.array([0, 40, 40])
    upper_bound = np.array([180, 255, 255])
    color_mask = cv2.inRange(hsv, lower_bound, upper_bound)

    # Exclude the bright neon green indicator boxes so we only analyze the inner core shape
    lower_green = np.array([40, 50, 50])
    upper_green = np.array([80, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)

    # Subtract green box lines from analysis channel matrix
    core_mask = cv2.subtract(color_mask, green_mask)

    kernel = np.ones((3, 3), np.uint8)
    core_mask = cv2.morphologyEx(core_mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(
        core_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    return contours


def calculate_spatial_metrics(contour, frame_w: int, frame_h: int) -> dict:
    M = cv2.moments(contour)
    if M["m00"] == 0:
        return None
    cx, cy = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
    x, y, w, h = cv2.boundingRect(contour)
    return {
        "pixel_x": cx,
        "pixel_y": cy,
        "box": (x, y, w, h),
        "percentage_x": round((cx / frame_w) * 100, 2),
        "percentage_y": round((cy / frame_h) * 100, 2),
    }


def save_cropped_target(
    img: np.ndarray, box: tuple, output_path: str, padding: int = 25
) -> bool:
    img_h, img_w, _ = img.shape
    x, y, w, h = box
    y1, y2 = max(0, y - padding), min(img_h, y + h + padding)
    x1, x2 = max(0, x - padding), min(img_w, x + w + padding)
    return cv2.imwrite(output_path, img[y1:y2, x1:x2])


def write_manifest_json(output_dir: str, file_name: str, payload: dict):
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, file_name), "w") as f:
        json.dump(payload, f, indent=4)


def analyze_satellite_image(image_path: str, output_dir: str = "assets/result") -> dict:
    """
    DECOUPLED ORCHESTRATOR: Pulls slices, routes metrics, maps geometries, and writes JSONs.
    """
    sector_base = os.path.splitext(os.path.basename(image_path))[0]
    report = {
        "status": "success",
        "total_detected": 0,
        "sector_file": os.path.basename(image_path),
        "data": [],
        "message": "",
    }

    img = cv2.imread(image_path)
    if img is None:
        report["status"] = "failed"
        report["message"] = f"Reading error on {image_path}"
        write_manifest_json(output_dir, f"{sector_base}_manifest.json", report)
        return report

    frame_h, frame_w, _ = img.shape
    contours = extract_combined_target_contours(img)

    detected_count = 0
    for contour in contours:
        if cv2.contourArea(contour) < 40:
            continue

        metrics = calculate_spatial_metrics(contour, frame_w, frame_h)
        if not metrics:
            continue

        detected_count += 1
        crop_name = f"{sector_base}_target_{detected_count}.png"
        crop_path = os.path.join(output_dir, crop_name)

        save_cropped_target(img, metrics["box"], crop_path)

        # Determine exactly what type of asset this contour represents
        resolved_type = classify_object_contour(contour)

        report["data"].append(
            {
                "target_id": f"TARGET-{sector_base}-{detected_count}",
                "object_type": resolved_type,
                "crop_asset_path": crop_path,
                "coordinates": {
                    "pixel_x": metrics["pixel_x"],
                    "pixel_y": metrics["pixel_y"],
                    "percentage_x": metrics["percentage_x"],
                    "percentage_y": metrics["percentage_y"],
                },
            }
        )

    report["total_detected"] = detected_count
    write_manifest_json(output_dir, f"{sector_base}_manifest.json", report)
    return report
