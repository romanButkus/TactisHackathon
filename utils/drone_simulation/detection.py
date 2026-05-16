import os

import cv2
import numpy as np

from utils.drone_simulation.models.objects import OBJECT_PROFILES

# =========================
# OBJECT DETECTION ENGINE
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
    """
    Detects tactical shapes within a sector and filters out duplicates that may have
    already been found in adjacent overlapping sectors.
    """
    if existing_detections is None:
        existing_detections = []

    ox, oy = origin
    sw, sh = size
    gw, gh = global_map_dim

    detections = []
    obj_id = obj_start_id

    # Distance threshold (in pixels) on the global map.
    # If a target of the same type is within this radius, it's considered a duplicate.
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

            # Local coordinates of the center point within this sector picture
            local_cx = int(M["m10"] / M["m00"])
            local_cy = int(M["m01"] / M["m00"])

            # 1. Calculate Global Position to cross-examine duplicates
            global_cx = ox + local_cx
            global_cy = oy + local_cy

            # 2. Check against objects already found in previous sector loops
            is_duplicate = False
            for existing in existing_detections:
                if existing["type"] == profile["type"]:
                    if "global_pixel_center" in existing:
                        ex_gx, ex_gy = existing["global_pixel_center"]
                    else:
                        continue  # Skip tracking if metadata is missing

                    distance = np.sqrt(
                        (global_cx - ex_gx) ** 2 + (global_cy - ex_gy) ** 2
                    )
                    if distance < DUPLICATE_RADIUS_THRESHOLD:
                        is_duplicate = True
                        break

            if is_duplicate:
                continue  # Skip adding this target entirely, ignoring edge-case splits!

            # Local bounding box within this sector picture
            x, y, w, h = cv2.boundingRect(cnt)

            obj_id += 1

            detections.append(
                {
                    "id": obj_id,
                    "type": profile["type"],
                    "sector": sector_id,
                    "local_pixel_center": [local_cx, local_cy],
                    "local_bbox": [x, y, w, h],
                    # Stored temporarily so subsequent sector loops can cross-reference it
                    "global_pixel_center": [global_cx, global_cy],
                }
            )

            # Dynamically feed this object back into our master check loop tracker
            existing_detections.append(detections[-1])

    return detections


# =========================
# THEATER SECTOR SCANNER
# =========================


def scan_sectors_from_memory(sector_crops, grid_size, global_map_dim, time_tick):
    # This array will serve as the persistent checklist across ALL sector grid blocks
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

            # Pass the accumulator array forward so detect_objects remembers previous seams
            sector_detections = detect_objects(
                img=img,
                sector_id=sector_id,
                origin=(c * sector_w, r * sector_h),
                size=(sector_w, sector_h),
                global_map_dim=global_map_dim,
                obj_start_id=global_obj_id,
                existing_detections=master_tick_detections,  # <--- Deduplication Sync
            )

            for d in sector_detections:
                global_obj_id += 1

                # Read updated key 'local_bbox' seamlessly
                x, y, w, h = d["local_bbox"]
                local_cx, local_cy = d["local_pixel_center"]

                # Slicing bounding window calculations
                pad = 20
                y1, y2 = max(0, y - pad), min(sector_h, y + h + pad)
                x1, x2 = max(0, x - pad), min(sector_w, x + w + pad)

                # CALCULATE CROP COORDINATES: Find center relative strictly to the saved snippet image
                crop_cx = local_cx - x1
                crop_cy = local_cy - y1
                d["crop_pixel"] = [crop_cx, crop_cy]

                # Crop and write thumbnail context file
                crop = img[y1:y2, x1:x2]
                filename = f"{tick_dir}/sector_{sector_id}_obj_{d['id']}.png"
                cv2.imwrite(filename, crop)

                d["image"] = filename

            # Keep master_tick_detections completely updated for the subsequent sector lookups

    # CLEAN-UP: Strip away the global calculation coordinates right before serialization
    # to keep your output telemetry JSON clean and readable for your dashboard.
    for d in master_tick_detections:
        if "global_pixel_center" in d:
            del d["global_pixel_center"]

    return master_tick_detections
