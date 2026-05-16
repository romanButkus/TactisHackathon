import os
import random

import cv2
import numpy as np

# Operational State Mapping for the Simulation Space
OBJECT_PROFILES = [
    {"type": "AMMO_DEPOT", "color": (0, 0, 255)},  # Pure Crimson Red (Triangle)
    {"type": "COMMS_CENTER", "color": (0, 165, 255)},  # Tactical Orange (Square)
    {
        "type": "TROOP_FORMATION",
        "color": (255, 0, 128),
    },  # Deep Violet/Magenta (Diamond)
]


def calculate_safe_sector_center(row: int, col: int, sec_w: int, sec_h: int) -> tuple:
    """
    Calculates a target center point forced safely inside a sector's inner window
    to avoid cutting off structural shapes on grid borders.
    """
    sec_x1 = col * sec_w
    sec_y1 = row * sec_h

    # Maintain high visibility by leaving clear margins from sector walls
    margin_x = int(sec_w * 0.25)
    margin_y = int(sec_h * 0.25)

    rx = random.randint(sec_x1 + margin_x, sec_x1 + sec_w - margin_x)
    ry = random.randint(sec_y1 + margin_y, sec_y1 + sec_h - margin_y)

    return rx, ry


def draw_tactical_shape(
    img: np.ndarray, obj_type: str, center: tuple, radius: int, color: tuple
):
    """
    Renders precise geometric vector shapes directly onto the map canvas matrix layers.
    """
    cx, cy = center

    if obj_type == "AMMO_DEPOT":
        # 🔺 Draw an upright triangle
        pts = np.array(
            [[cx, cy - radius], [cx - radius, cy + radius], [cx + radius, cy + radius]],
            np.int32,
        )
        cv2.fillPoly(img, [pts], color)

    elif obj_type == "COMMS_CENTER":
        # ⏹️ Draw a clean solid square block
        cv2.rectangle(
            img, (cx - radius, cy - radius), (cx + radius, cy + radius), color, -1
        )

    elif obj_type == "TROOP_FORMATION":
        # 🔶 Draw a standard military tactical diamond (Rhombus)
        pts = np.array(
            [
                [cx, cy - radius],  # Top point
                [cx + radius, cy],  # Right point
                [cx, cy + radius],  # Bottom point
                [cx - radius, cy],  # Left point
            ],
            np.int32,
        )
        cv2.fillPoly(img, [pts], color)


def slice_and_save_grid(
    master_map: np.ndarray,
    grid_size: int,
    sec_w: int,
    sec_h: int,
    height: int,
    width: int,
):
    """
    Iterates systematically across the canvas matrix and writes localized sector snapshots to disk.
    """
    sector_count = 0
    for row in range(grid_size):
        for col in range(grid_size):
            sector_count += 1

            y1 = row * sec_h
            y2 = height if row == grid_size - 1 else (row + 1) * sec_h
            x1 = col * sec_w
            x2 = width if col == grid_size - 1 else (col + 1) * sec_w

            sector_crop = master_map[y1:y2, x1:x2]
            cv2.imwrite(f"assets/test/{sector_count}.png", sector_crop)
    return sector_count


def generate_tactical_simulation(
    large_map_path: str, grid_size: int = 10, total_targets: int = 30
) -> list:
    """
    STRATIFIED ORCHESTRATOR FUNCTION: Enforces structured distribution tracking
    so that a minimum uniform quota of each shape classification is drawn.
    """
    master_map = cv2.imread(large_map_path)
    if master_map is None:
        print(f"❌ Error: Master map file not found at {large_map_path}")
        return None

    height, width, _ = master_map.shape
    os.makedirs("assets/test", exist_ok=True)
    os.makedirs("assets/result", exist_ok=True)

    sector_width = width // grid_size
    sector_height = height // grid_size

    target_locations = []

    # Pre-calculate an even assortment pool via a Round-Robin Indexer
    # For 30 targets, this automatically yields exactly 10 of each type
    all_available_sectors = [(r, c) for r in range(grid_size) for c in range(grid_size)]
    random.shuffle(
        all_available_sectors
    )  # Ensure they spread out visually across the map

    print(
        f"🎯 Enforcing uniform quota scattering: Generating {total_targets} target points..."
    )

    for idx in range(total_targets):
        if idx >= len(all_available_sectors):
            break  # Prevent index errors if requested count exceeds grid limits

        rand_row, rand_col = all_available_sectors[idx]
        sector_id = (rand_row * grid_size) + rand_col + 1

        rx, ry = calculate_safe_sector_center(
            rand_row, rand_col, sector_width, sector_height
        )

        # Increase radius bounds slightly so the shapes stand out clearer on 4K maps
        radius = random.randint(24, 32)

        # STRATIFIED SELECTOR: Loops cleanly through your profiles (0, 1, 2, 0, 1, 2...)
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

        # Render a clear neon green high-contrast bounding frame
        box_padding = radius + 15
        cv2.rectangle(
            master_map,
            (rx - box_padding, ry - box_padding),
            (rx + box_padding, ry + box_padding),
            (0, 255, 0),
            3,
        )

        # Inject the custom target architecture overlay
        draw_tactical_shape(
            master_map, profile["type"], (rx, ry), radius, profile["color"]
        )

    cv2.imwrite("assets/test/master_theater_map.png", master_map)

    # Process sector slicing operations
    total_sectors = slice_and_save_grid(
        master_map, grid_size, sector_width, sector_height, height, width
    )

    # Print out summary statistics for your validation checks
    type_counts = {}
    for t in target_locations:
        type_counts[t["expected_type"]] = type_counts.get(t["expected_type"], 0) + 1

    print(f"✅ Simulation space partitioned into {total_sectors} matrix sector zones.")
    print(f"📊 Injection Balance Profile: {type_counts}")

    return target_locations
