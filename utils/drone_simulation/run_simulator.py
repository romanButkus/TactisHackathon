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

        pixel_key = "global_pixel" if "global_pixel" in t else "global_pixel_center"

        # If accessing raw fallback tracking coordinates, make sure arrays contain standard ints
        if type(t[pixel_key]) is list:
            t[pixel_key][0] = int(np.clip(t[pixel_key][0] + dx, 60, w - 60))
            t[pixel_key][1] = int(np.clip(t[pixel_key][1] + dy, 60, h - 60))


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
        pixel_key = "global_pixel" if "global_pixel" in t else "global_pixel_center"

        draw_tactical_shape(
            canvas,
            t["type"],
            (int(t[pixel_key][0]), int(t[pixel_key][1])),
            radius,
            profile["color"],
        )

    os.makedirs("assets/test", exist_ok=True)
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
# DETECTION ENGINE
# =========================


def detect_objects(
    img,
    sector_id,
    origin,
    size,
    global_map_dim,
    obj_start_id=0,
    existing_detections=None,
):
    if existing_detections is None:
        existing_detections = []

    ox, oy = origin
    sw, sh = size
    gw, gh = global_map_dim

    detections = []
    obj_id = obj_start_id
    DUPLICATE_RADIUS_THRESHOLD = 35

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

            local_cx = int(M["m10"] / M["m00"])
            local_cy = int(M["m01"] / M["m00"])
            global_cx = ox + local_cx
            global_cy = oy + local_cy

            is_duplicate = False
            for existing in existing_detections:
                if existing["type"] == profile["type"]:
                    if "global_pixel_center" in existing:
                        ex_gx, ex_gy = existing["global_pixel_center"]
                    else:
                        continue

                    distance = np.sqrt(
                        (global_cx - ex_gx) ** 2 + (global_cy - ex_gy) ** 2
                    )
                    if distance < DUPLICATE_RADIUS_THRESHOLD:
                        is_duplicate = True
                        break

            if is_duplicate:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            obj_id += 1

            detections.append(
                {
                    "id": obj_id,
                    "type": profile["type"],
                    "sector": sector_id,
                    "local_pixel_center": [local_cx, local_cy],
                    "local_bbox": [x, y, w, h],
                    "global_pixel_center": [global_cx, global_cy],
                }
            )
            existing_detections.append(detections[-1])

    return detections


# =========================
# SCAN MEMORY
# =========================


def scan_sectors_from_memory(sector_crops, grid_size, global_map_dim, time_tick):
    master_tick_detections = []
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

            sector_detections = detect_objects(
                img=img,
                sector_id=sector_id,
                origin=(c * sector_w, r * sector_h),
                size=(sector_w, sector_h),
                global_map_dim=global_map_dim,
                obj_start_id=global_obj_id,
                existing_detections=master_tick_detections,
            )

            for d in sector_detections:
                global_obj_id += 1
                x, y, w, h = d["local_bbox"]
                local_cx, local_cy = d["local_pixel_center"]

                pad = 20
                y1, y2 = max(0, y - pad), min(sector_h, y + h + pad)
                x1, x2 = max(0, x - pad), min(sector_w, x + w + pad)

                crop_cx = local_cx - x1
                crop_cy = local_cy - y1
                d["crop_pixel"] = [crop_cx, crop_cy]

                crop = img[y1:y2, x1:x2]
                filename = f"{tick_dir}/sector_{sector_id}_obj_{d['id']}.png"
                cv2.imwrite(filename, crop)
                d["image"] = filename

    # Safely clean reference indices before packing structure
    for d in master_tick_detections:
        if "global_pixel_center" in d:
            del d["global_pixel_center"]

    return master_tick_detections


# ==========================================
# MASTER SIMULATION EXECUTIVE FUNCTION
# ==========================================


def run_theater_simulation(map_image_path: str = "assets/test_map.png"):
    """
    Executes the tactical simulation steps sequentially without any physical
    time delays. Compiles historical coordinates data instantly.

    Returns:
        dict: The full structured analytics run manifest ready for JSON parsing.
    """
    if not os.path.exists(map_image_path):
        return {
            "error": f"Target background environment resource '{map_image_path}' not found."
        }

    base_map = cv2.imread(map_image_path)
    gh, gw = base_map.shape[:2]

    grid_size = 5
    sector_w, sector_h = gw // grid_size, gh // grid_size

    os.makedirs("assets/test", exist_ok=True)
    os.makedirs("assets/result", exist_ok=True)

    temp_img = base_map.copy()
    combined_mask = np.zeros(base_map.shape[:2], dtype=np.uint8)

    for profile in OBJECT_PROFILES:
        target = np.full_like(temp_img, profile["color"], dtype=np.uint8)
        diff = cv2.absdiff(temp_img, target)
        dist = np.sum(diff, axis=2)
        mask = (dist < 120).astype(np.uint8) * 255
        combined_mask = cv2.bitwise_or(combined_mask, mask)

    combined_mask = cv2.dilate(
        combined_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=1
    )
    clean_background_map = cv2.inpaint(base_map, combined_mask, 7, cv2.INPAINT_TELEA)

    tracked_targets_memory = []
    total_duration_sec = 120
    interval_sec = 20
    total_ticks = total_duration_sec // interval_sec

    all_simulation_ticks_history = {}

    for tick in range(1, total_ticks + 1):
        if tick == 1:
            initial_sector_crops = {}
            s_id = 0
            for r in range(grid_size):
                for c in range(grid_size):
                    s_id += 1
                    x1, y1 = c * sector_w, r * sector_h
                    crop = base_map[y1 : y1 + sector_h, x1 : x1 + sector_w]
                    initial_sector_crops[s_id] = crop

            detections = scan_sectors_from_memory(
                initial_sector_crops, grid_size, (gw, gh), time_tick=tick
            )
            tracked_targets_memory = detections

            if len(tracked_targets_memory) == 0:
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

        sector_crops = build_and_slice_theater_memory(
            clean_background_map, tracked_targets_memory, grid_size, sector_w, sector_h
        )

        detections = scan_sectors_from_memory(
            sector_crops, grid_size, (gw, gh), time_tick=tick
        )

        # Caches backup JSON steps locally
        with open(f"assets/result/detections_t{tick}.json", "w") as f:
            json.dump({"tick": tick, "objects": detections}, f, indent=2)

        all_simulation_ticks_history[f"tick_{tick}"] = {
            "tick": tick,
            "timestamp_sec": tick * interval_sec,
            "object_count": len(detections),
            "objects": detections,
        }

    # Compile the final dictionary manifest layout
    manifest_payload = {
        "simulation_summary": {
            "total_ticks_recorded": total_ticks,
            "interval_seconds": interval_sec,
            "map_dimensions": [gw, gh],
        },
        "timeline": all_simulation_ticks_history,
    }

    # Save tracking file as history record
    with open("assets/result/all_ticks_manifest.json", "w") as master_f:
        json.dump(manifest_payload, master_f, indent=2)

    return manifest_payload
