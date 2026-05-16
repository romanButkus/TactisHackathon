import os

import httpx
from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]

load_dotenv()
API_KEY = os.getenv("CELL_API_KEY")


def fetch_cell_tower_data():
    """
    Queries the OpenCellID API for cell towers inside a specific geographic area
    using httpx, returning the raw data array.
    """
    # 1. Ensure the API key is loaded correctly from your environment variables
    if not API_KEY:
        print("❌ Error: CELL_API_KEY environment variable is missing or empty.")
        return []

    url = "https://opencellid.org/cell/getInArea"
    params = {"key": API_KEY, "BBOX": "19.3,59.7,21.1,60.5", "format": "json"}

    print("🛰️ Initiating network request to OpenCellID telemetry endpoints via httpx...")

    try:
        response = httpx.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        cells = data.get("cells", [])

        print(
            f"Successfully extracted {len(cells)} active cell profiles from regional data matrix."
        )
        return cells

    except httpx.HTTPStatusError as exc:
        print(f"HTTP Status Error: {exc.response.status_code} - {exc.response.text}")
        return []
    except httpx.RequestError as exc:
        print(
            f"Network Connectivity/Protocol Error occurred while requesting data: {exc}"
        )
        return []
    except ValueError:
        print(
            "Data Parsing Error: The endpoint response could not be translated into a valid JSON object."
        )
        return []


if __name__ == "__main__":
    # The Real Deal live sanity check
    towers = fetch_cell_tower_data()
    print(f"Total Towers Recovered: {len(towers)}")
    if towers:
        print(f"Sample Tower Payload Data: {towers[0]}")
