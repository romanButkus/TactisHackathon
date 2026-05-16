import os
import random

import cv2
import numpy as np

OBJECT_PROFILES = [
    {"type": "AMMO_DEPOT", "color": (0, 0, 255)},  # 🔺 Crimson Red
    {"type": "COMMS_CENTER", "color": (0, 165, 255)},  # ⏹️ Tactical Orange
    {"type": "TROOP_FORMATION", "color": (255, 0, 128)}, 
    {"type": "COMMAND_POST", "color": (0, 230, 230)},  
]


def draw_tactical_shape(
    img: np.ndarray, obj_type: str, center: tuple, radius: int, color: tuple
):
    cx, cy = center
    if obj_type == "AMMO_DEPOT":
        pts = np.array(
            [[cx, cy - radius], [cx - radius, cy + radius], [cx + radius, cy + radius]],
            np.int32,
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
            ],
            np.int32,
        )
        cv2.fillPoly(img, [pts], color)
    elif obj_type == "COMMAND_POST":
        pts = [
            [
                int(cx + radius * np.cos(np.deg2rad(i * 60 + 30))),
                int(cy + radius * np.sin(np.deg2rad(i * 60 + 30))),
            ]
            for i in range(6)
        ]
        cv2.fillPoly(img, [np.array(pts, np.int32)], color)


def generate_tactical_simulation(
    large_map_path: str, grid_size: int = 10, total_targets: int = 20
):
    master_map = cv2.imread(large_map_path)
    if master_map is None:
        print(f"❌ Error: Master map file not found at {large_map_path}")
        return None

    height, width, _ = master_map.shape
    os.makedirs("assets/test", exist_ok=True)
    os.makedirs("assets/result", exist_ok=True)

    sector_width, sector_height = width // grid_size, height // grid_size
    target_locations = []

    all_available_sectors = [(r, c) for r in range(grid_size) for c in range(grid_size)]
    random.shuffle(all_available_sectors)

    for idx in range(total_targets):
        if idx >= len(all_available_sectors):
            break
        rand_row, rand_col = all_available_sectors[idx]
        sector_id = (rand_row * grid_size) + rand_col + 1

        sec_x1, sec_y1 = rand_col * sector_width, rand_row * sector_height
        margin_x, margin_y = int(sector_width * 0.25), int(sector_height * 0.25)

        rx = random.randint(sec_x1 + margin_x, sec_x1 + sector_width - margin_x)
        ry = random.randint(sec_y1 + margin_y, sec_y1 + sector_height - margin_y)
        radius = random.randint(26, 32)
        profile = OBJECT_PROFILES[idx % len(OBJECT_PROFILES)]

        target_locations.append(
            {
                "x": rx,
                "y": ry,
                "radius": radius,
                "assigned_sector": sector_id,
                "expected_type": profile["type"],
            }
        )

        # Draw Neon Green Tracking Box
        box_pad = radius + 15
        cv2.rectangle(
            master_map,
            (rx - box_pad, ry - box_pad),
            (rx + box_pad, ry + box_pad),
            (0, 255, 0),
            3,
        )

        # Draw Target Shape
        draw_tactical_shape(
            master_map, profile["type"], (rx, ry), radius, profile["color"]
        )

    cv2.imwrite("assets/test/master_theater_map.png", master_map)

    sector_count = 0
    for row in range(grid_size):
        for col in range(grid_size):
            sector_count += 1
            y1, y2 = (
                row * sector_height,
                height if row == grid_size - 1 else (row + 1) * sector_height,
            )
            x1, x2 = (
                col * sector_width,
                width if col == grid_size - 1 else (col + 1) * sector_width,
            )
            cv2.imwrite(f"assets/test/{sector_count}.png", master_map[y1:y2, x1:x2])

    type_counts = {}
    for t in target_locations:
        type_counts[t["expected_type"]] = type_counts.get(t["expected_type"], 0) + 1

    print(f"✅ Generated {total_targets} targets across {sector_count} sectors.")
    print(f"📊 Deployed: {type_counts}")
    return target_locations
