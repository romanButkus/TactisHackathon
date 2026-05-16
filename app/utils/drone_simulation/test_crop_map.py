import json
import os
import random

import cv2
import numpy as np

# =========================
# OBJECT DEFINITIONS
# =========================

OBJECT_PROFILES = [
    {"type": "AMMO_DEPOT", "color": (0, 0, 255)},  # red
    {"type": "COMMS_CENTER", "color": (0, 165, 255)},  # orange
    {"type": "TROOP_FORMATION", "color": (255, 0, 128)},  # pink
    {"type": "COMMAND_POST", "color": (0, 230, 230)},  # cyan
]


# =========================
# DRAW SHAPES
# =========================


def draw_tactical_shape(img, obj_type, center, radius, color):
    cx, cy = center

    if obj_type == "AMMO_DEPOT":
        pts = np.array(
            [[cx, cy - radius], [cx - radius, cy + radius], [cx + radius, cy + radius]]
        )
        cv2.fillPoly(img, [pts], color)

    elif obj_type == "COMMS_CENTER":
        cv2.rectangle(
            img, (cx - radius, cy - radius), (cx + radius, cy + radius), color, -1
        )

    elif obj_type == "TROOP_FORMATION":
        pts = np.array(
            [
                [cx, cy - radius],
                [cx + radius, cy],
                [cx, cy + radius],
                [cx - radius, cy],
            ]
        )
        cv2.fillPoly(img, [pts], color)

    elif obj_type == "COMMAND_POST":
        pts = [
            (
                int(cx + radius * np.cos(np.deg2rad(i * 60 + 30))),
                int(cy + radius * np.sin(np.deg2rad(i * 60 + 30))),
            )
            for i in range(6)
        ]
        cv2.fillPoly(img, [np.array(pts, np.int32)], color)


# =========================
# MAP GENERATION
# =========================


def generate_tactical_simulation(map_path, grid_size=5, total_targets=12):
    img = cv2.imread(map_path)
    if img is None:
        raise FileNotFoundError("Map not found")

    h, w = img.shape[:2]

    sector_w = w // grid_size
    sector_h = h // grid_size

    os.makedirs("assets/test", exist_ok=True)
    os.makedirs("assets/result", exist_ok=True)

    sectors = [(r, c) for r in range(grid_size) for c in range(grid_size)]
    random.shuffle(sectors)

    for i in range(total_targets):
        r, c = sectors[i]

        x1, y1 = c * sector_w, r * sector_h

        rx = random.randint(x1 + 20, x1 + sector_w - 20)
        ry = random.randint(y1 + 20, y1 + sector_h - 20)

        radius = random.randint(20, 35)

        profile = OBJECT_PROFILES[i % len(OBJECT_PROFILES)]

        draw_tactical_shape(img, profile["type"], (rx, ry), radius, profile["color"])

    cv2.imwrite("assets/test/master.png", img)

    # crop sectors
    sector_id = 0
    for r in range(grid_size):
        for c in range(grid_size):
            sector_id += 1

            x1, y1 = c * sector_w, r * sector_h
            crop = img[y1 : y1 + sector_h, x1 : x1 + sector_w]

            cv2.imwrite(f"assets/test/{sector_id}.png", crop)

    return (sector_w, sector_h)


# =========================
# DETECTION
# =========================


def detect_objects(img, sector_id, origin, size, obj_start_id=0):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    ox, oy = origin
    sw, sh = size

    detections = []
    obj_id = obj_start_id

    for profile in OBJECT_PROFILES:
        bgr = np.uint8([[profile["color"]]])
        hsv_color = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]

        lower = np.array([max(0, hsv_color[0] - 10), 100, 100])
        upper = np.array([min(179, hsv_color[0] + 10), 255, 255])

        mask = cv2.inRange(hsv, lower, upper)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            if cv2.contourArea(cnt) < 80:
                continue

            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            x, y, w, h = cv2.boundingRect(cnt)

            obj_id += 1

            detections.append(
                {
                    "id": obj_id,
                    "type": profile["type"],
                    "sector": sector_id,
                    "sector_center": [cx, cy],
                    "global_center": [ox + cx, oy + cy],
                    "bbox": [x, y, w, h],
                }
            )

    return detections


# =========================
# SCAN SECTORS + SAVE CROPS
# =========================


def scan_sectors(grid_size):
    results = []

    os.makedirs("assets/result/detections", exist_ok=True)

    sector_id = 0
    global_obj_id = 0

    for r in range(grid_size):
        for c in range(grid_size):
            sector_id += 1

            path = f"assets/test/{sector_id}.png"
            img = cv2.imread(path)

            if img is None:
                continue

            h, w = img.shape[:2]

            detections = detect_objects(
                img,
                sector_id,
                origin=(c * w, r * h),
                size=(w, h),
                obj_start_id=global_obj_id,
            )

            for d in detections:
                global_obj_id += 1

                x, y, w_box, h_box = d["bbox"]

                crop = img[y : y + h_box, x : x + w_box]

                filename = (
                    f"assets/result/detections/sector_{sector_id}_obj_{d['id']}.png"
                )
                cv2.imwrite(filename, crop)

                d["image"] = filename

                results.append(d)

    return results


# =========================
# EXPORT JSON
# =========================


def export_json(data):
    with open("assets/result/detections.json", "w") as f:
        json.dump({"count": len(data), "objects": data}, f, indent=2)


# =========================
# RUN TEST
# =========================


def main():
    map_path = "assets/test_map.png"

    if not os.path.exists(map_path):
        raise FileNotFoundError(f"Missing map: {map_path}")

    print("🧠 Generating simulation...")
    grid_size = 5

    generate_tactical_simulation(map_path, grid_size=grid_size, total_targets=12)

    print("🔍 Scanning sectors...")
    detections = scan_sectors(grid_size)

    export_json(detections)

    print("\n✅ DONE")
    print(f"Objects detected: {len(detections)}")
    print("Saved: assets/result/detections.json")


if __name__ == "__main__":
    main()
