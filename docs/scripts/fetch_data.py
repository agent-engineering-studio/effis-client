"""Download the live EFFIS data behind the README figures.

Usage: uv run python docs/scripts/fetch_data.py <out-dir>
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

import httpx

from effis_client import COMPONENTS, WMS_URL, check_tiff, fetch_perimeters, fwi_params

#: Basilicata and its surroundings, (west, south, east, north).
PERIMETERS_BBOX = (15.3, 39.85, 16.9, 41.15)
#: Italy, for the FWI maps.
FWI_BBOX = (6.0, 36.0, 19.0, 47.5)
FWI_DAY = date(2026, 8, 1)


async def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120) as client:
        perimeters = await fetch_perimeters(
            client, PERIMETERS_BBOX, start=date(2012, 1, 1), end=date(2026, 12, 31)
        )
        print(f"perimeters: {len(perimeters.features)}, truncated={perimeters.truncated}")
        collection = {"type": "FeatureCollection", "features": perimeters.features}
        (out / "basilicata.geojson").write_text(json.dumps(collection))

        for component in COMPONENTS:
            response = await client.get(
                WMS_URL, params=fwi_params(FWI_DAY, FWI_BBOX, component=component)
            )
            response.raise_for_status()
            tiff = check_tiff(response.headers.get("content-type", ""), response.content)
            (out / f"italy_{component}.tif").write_bytes(tiff)
            print(f"{component}: {len(tiff)} bytes")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
