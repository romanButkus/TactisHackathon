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
    """Draws a predefined tactical polygon shape onto a given image canvas.

    Parameters:
        img (numpy.ndarray): The source BGR image array to draw upon.
        obj_type (str): The classification type determining the geometry
                        ('AMMO_DEPOT', 'COMMS_CENTER', 'TROOP_FORMATION', 'COMMAND_POST').
        center (tuple): A tuple of (x, y) integers marking the shape's midpoint.
        radius (int): Pixel radius or bounding extent of the polygon asset.
        color (tuple): BGR color tuple representing the shape profile fill.

    Returns:
        None
    """
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

    cv2.fillPoly(img, [pts.astype(np.int32)], color)  # pyright: ignore[reportPossiblyUnboundVariable]


# =========================
# SHIFT OBJECTS
# =========================


def apply_positional_shift(tracked_targets, h, w):
    """Applies a random positional translation to existing tracking targets.

    Simulates kinematic drift over time ticks while keeping coordinates bound
    safely within the global theater boundaries.

    Parameters:
        tracked_targets (list): Cumulative active target list from memory tracking.
        h (int): Total pixel height of the global map image environment.
        w (int): Total pixel width of the global map image environment.

    Returns:
        None (Modifies target lists in place)
    """
    for t in tracked_targets:
        dx = random.randint(-25, 25)
        dy = random.randint(-25, 25)

        # Handle formatting keys dynamically if seeded directly from detection output dictionaries
        pixel_key = "global_pixel" if "global_pixel" in t else "global_pixel_center"

        t[pixel_key][0] = np.clip(t[pixel_key][0] + dx, 60, w - 60)
        t[pixel_key][1] = np.clip(t[pixel_key][1] + dy, 60, h - 60)


# =========================
# DRAW + SLICE MAP
# =========================


def build_and_slice_theater_memory(
    clean_map_img, tracked_targets, grid_size, sector_w, sector_h
):
    """Renders active objects onto a clean map and slices the terrain into an indexed sector grid dictionary.

    Parameters:
        clean_map_img (numpy.ndarray): Background environment image without shapes.
        tracked_targets (list): Collection dictionary containing positions of targets to render.
        grid_size (int): Dimension of the square sector matrix (e.g., 5 for a 5x5 grid).
        sector_w (int): Sliced block pixel width configuration.
        sector_h (int): Sliced block pixel height configuration.

    Returns:
        dict: A lookup table linking sequential 1-based sector IDs to cropped numpy sub-images.
    """
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
    """Processes a sector crop image to detect tactical targets, filtering out boundary seams.

    Utilizes absolute proximity checks on a persistent checklist to discard targets
    already logged by adjacent grid zones.

    Parameters:
        img (numpy.ndarray): Cropped sector grid image slice.
        sector_id (int): Numeric identifier of the current sector window.
        origin (tuple): Global pixel coordinate offset tuple (ox, oy) of this sector's top-left corner.
        size (tuple): Current dimensions (sw, sh) of this sector segment.
        global_map_dim (tuple): Absolute global background dimensions (gw, gh).
        obj_start_id (int, optional): Initial indexing value offset for object unique identification.
        existing_detections (list, optional): Running list reference storing targets found during this tick.

    Returns:
        list: Filtered detection dictionaries identifying unique structures in this sector block.
    """
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
    """Orchestrates multi-sector detection processing over an entire tick grid layout.

    Crops localized object visual assets with custom padding windows and builds
    unbiased center vectors for each asset output.

    Parameters:
        sector_crops (dict): Active lookup table linking sector IDs to sub-images.
        grid_size (int): Dimensions of the grid matrix.
        global_map_dim (tuple): Absolute global backplate tracking dimensions (gw, gh).
        time_tick (int): Current sequential scenario timeline execution tick.

    Returns:
        list: Consolidated array of unique target detections compiled across all grids.
    """
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

    for d in master_tick_detections:
        if "global_pixel_center" in d:
            del d["global_pixel_center"]

    return master_tick_detections


# =========================
# MAIN EXECUTIVE PIPELINE
# =========================


def main():
    """Main execution script managing database creation, system simulations,

    image inpainting backplate generations, timeline steps, and structured file generation.
    """
    map_path = "assets/test_map.png"
    if not os.path.exists(map_path):
        raise FileNotFoundError(map_path)

    base_map = cv2.imread(map_path)
    gh, gw = base_map.shape[:2]  # pyright: ignore[reportOptionalMemberAccess]

    grid_size = 5
    sector_w, sector_h = gw // grid_size, gh // grid_size

    os.makedirs("assets/test", exist_ok=True)
    os.makedirs("assets/result", exist_ok=True)

    print("🧹 Generating clean environment backplate...")
    clean_background_map = base_map.copy()

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

    # Master database tracking manifest dictionary to store timeline ticks
    all_simulation_ticks_history = {}

    for tick in range(1, total_ticks + 1):
        print(f"\n[TICK {tick}]")

        if tick == 1:
            print("Parsing baseline targets directly from the source map file...")
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
            print(
                f"🎯 Seeded pipeline tracker with {len(tracked_targets_memory)} initial map items."
            )

            if len(tracked_targets_memory) == 0:
                print(
                    "⚠️ No objects found on test_map.png. Generating fallback targets..."
                )
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
            clean_background_map,
            tracked_targets_memory,
            grid_size,
            sector_w,
            sector_h,
        )

        detections = scan_sectors_from_memory(
            sector_crops, grid_size, (gw, gh), time_tick=tick
        )

        # Write out single individual step file for caching
        with open(f"assets/result/detections_t{tick}.json", "w") as f:
            json.dump({"tick": tick, "objects": detections}, f, indent=2)

        # Log this step data directly to our unified run history object memory
        all_simulation_ticks_history[f"tick_{tick}"] = {
            "tick": tick,
            "timestamp_sec": tick * interval_sec,
            "object_count": len(detections),
            "objects": detections,
        }

        print("Detected unique structures:", len(detections))

        if tick < total_ticks:
            time.sleep(interval_sec)

    # ==========================================
    # WRITE UNIFIED MASTER RUN JSON MANIFEST
    # ==========================================
    combined_json_path = "assets/result/all_ticks_manifest.json"
    print(f"\n💾 Compiling history database into a single file...")
    with open(combined_json_path, "w") as master_f:
        json.dump(
            {
                "simulation_summary": {
                    "total_ticks_recorded": total_ticks,
                    "interval_seconds": interval_sec,
                    "map_dimensions": [gw, gh],
                },
                "timeline": all_simulation_ticks_history,
            },
            master_f,
            indent=2,
        )
    print(
        f"✅ Unified manifest successfully compiled and written to: {combined_json_path}"
    )


if __name__ == "__main__":
    main()
