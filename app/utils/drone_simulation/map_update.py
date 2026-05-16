import json
import os
import random
import time

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

    elif obj_type == "COMMS_CENTER":
        cv2.rectangle(
            img, (cx - radius, cy - radius), (cx + radius, cy + radius), color, -1
        )
        return

    elif obj_type == "TROOP_FORMATION":
        pts = np.array(
            [[cx, cy - radius], [cx + radius, cy], [cx, cy + radius], [cx - radius, cy]]
        )

    elif obj_type == "COMMAND_POST":
        pts = np.array(
            [
                (
                    int(cx + radius * np.cos(np.deg2rad(i * 60 + 30))),
                    int(cy + radius * np.sin(np.deg2rad(i * 60 + 30))),
                )
                for i in range(6)
            ],
            np.int32,
        )

    cv2.fillPoly(img, [pts.astype(np.int32)], color)


# =========================
# SHIFT OBJECTS
# =========================


def apply_positional_shift(tracked_targets, h, w):
    for t in tracked_targets:
        dx = random.randint(-25, 25)
        dy = random.randint(-25, 25)

        t["global_pixel"][0] = np.clip(t["global_pixel"][0] + dx, 60, w - 60)
        t["global_pixel"][1] = np.clip(t["global_pixel"][1] + dy, 60, h - 60)


# =========================
# DRAW + SLICE MAP
# =========================


def build_and_slice_theater_memory(
    clean_map_img, tracked_targets, grid_size, sector_w, sector_h
):
    canvas = clean_map_img.copy()

    for t in tracked_targets:
        profile = next(p for p in OBJECT_PROFILES if p["type"] == t["type"])

        radius = t.get("radius", 25)

        draw_tactical_shape(
            canvas,
            t["type"],
            (int(t["global_pixel"][0]), int(t["global_pixel"][1])),
            radius,
            profile["color"],
        )

    cv2.imwrite("assets/test/master.png", canvas)

    sector_crops = {}
    sector_id = 0

    for r in range(grid_size):
        for c in range(grid_size):
            sector_id += 1
            x1, y1 = c * sector_w, r * sector_h
            crop = canvas[y1 : y1 + sector_h, x1 : x1 + sector_w]

            cv2.imwrite(f"assets/test/{sector_id}.png", crop)
            sector_crops[sector_id] = crop

    return sector_crops


# =========================
# DETECTION (FIXED)
# =========================


def detect_objects(img, sector_id, origin, size, global_map_dim, obj_start_id=0):
    ox, oy = origin
    sw, sh = size
    gw, gh = global_map_dim

    detections = []
    obj_id = obj_start_id

    for profile in OBJECT_PROFILES:
        target = np.full_like(img, profile["color"], dtype=np.uint8)
        diff = cv2.absdiff(img, target)

        dist = np.sum(diff, axis=2)

        mask = (dist < 120).astype(np.uint8) * 255

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            if cv2.contourArea(cnt) < 20:
                continue

            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            x, y, w, h = cv2.boundingRect(cnt)
            global_x, global_y = ox + cx, oy + cy

            obj_id += 1

            detections.append(
                {
                    "id": obj_id,
                    "type": profile["type"],
                    "sector": sector_id,
                    "global_pixel": [global_x, global_y],
                    "bbox": [x, y, w, h],
                }
            )

    return detections


# =========================
# SCAN MEMORY
# =========================


def scan_sectors_from_memory(sector_crops, grid_size, global_map_dim, time_tick):
    results = []
    tick_dir = f"assets/result/detections_t{time_tick}"
    os.makedirs(tick_dir, exist_ok=True)

    gw, gh = global_map_dim
    sector_w, sector_h = gw // grid_size, gh // grid_size

    global_obj_id = 0

    for r in range(grid_size):
        for c in range(grid_size):
            sector_id = r * grid_size + c + 1
            img = sector_crops.get(sector_id)
            if img is None:
                continue

            detections = detect_objects(
                img,
                sector_id,
                origin=(c * sector_w, r * sector_h),
                size=(sector_w, sector_h),
                global_map_dim=global_map_dim,
                obj_start_id=global_obj_id,
            )

            for d in detections:
                global_obj_id += 1

                x, y, w, h = d["bbox"]

                pad = 20
                y1, y2 = max(0, y - pad), min(sector_h, y + h + pad)
                x1, x2 = max(0, x - pad), min(sector_w, x + w + pad)

                crop = img[y1:y2, x1:x2]

                filename = f"{tick_dir}/sector_{sector_id}_obj_{d['id']}.png"
                cv2.imwrite(filename, crop)

                d["image"] = filename
                results.append(d)

    return results


# =========================
# MAIN
# =========================


def main():
    map_path = "assets/test_map.png"
    if not os.path.exists(map_path):
        raise FileNotFoundError(map_path)

    base_map = cv2.imread(map_path)
    gh, gw = base_map.shape[:2]

    grid_size = 5
    sector_w, sector_h = gw // grid_size, gh // grid_size

    os.makedirs("assets/test", exist_ok=True)
    os.makedirs("assets/result", exist_ok=True)

    # clean background
    clean_background_map = base_map.copy()

    tracked_targets_memory = []

    total_duration_sec = 120
    interval_sec = 20
    total_ticks = total_duration_sec // interval_sec

    for tick in range(1, total_ticks + 1):
        print(f"\n[TICK {tick}]")

        # =========================
        # TICK 1 FIXED INIT
        # =========================
        if tick == 1:
            print("Initializing objects...")

            tracked_targets_memory = []

            for i in range(12):
                tracked_targets_memory.append(
                    {
                        "id": i,
                        "type": random.choice([p["type"] for p in OBJECT_PROFILES]),
                        "global_pixel": [
                            random.randint(100, gw - 100),
                            random.randint(100, gh - 100),
                        ],
                        "radius": random.randint(20, 40),
                    }
                )

        else:
            apply_positional_shift(tracked_targets_memory, gh, gw)

        # draw + slice ALWAYS
        sector_crops = build_and_slice_theater_memory(
            clean_background_map,
            tracked_targets_memory,
            grid_size,
            sector_w,
            sector_h,
        )

        detections = scan_sectors_from_memory(
            sector_crops, grid_size, (gw, gh), time_tick=tick
        )

        with open(f"assets/result/detections_t{tick}.json", "w") as f:
            json.dump({"tick": tick, "objects": detections}, f, indent=2)

        print("Detected:", len(detections))

        if tick < total_ticks:
            time.sleep(interval_sec)


if __name__ == "__main__":
    main()
