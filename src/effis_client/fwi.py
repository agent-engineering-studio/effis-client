"""The official EFFIS Fire Weather Index from its WMS, as numbers, not colours.

EFFIS publishes the FWI chain computed on Météo-France weather on the same
MapServer as the perimeters, but at ``/effis``, not ``/gwis``. Requested with
``FORMAT=image/tiff`` it returns a float32 GeoTIFF of raw values, which can
be sampled at any point.

Verified against the live service (2026-10-19, again 2026-11-02), and not
what the EFFIS documentation says:

* the layers are ``mf010.<component>`` (fwi, ffmc, dmc, dc, isi, bui); the
  ``ecmwf007.fwi`` of the EFFIS example answers ``LayerNotDefined``;
* ``TIME`` accepts past days, today and the next two; beyond that the
  answer is a 200 with a raster that is **all zeros** -- the absence of data,
  not a calm day. :func:`sample_fwi` returns ``None`` for it;
* the sea is zero on valid days too: a point on land reads its own pixel,
  and a single zero pixel stays a value;
* errors come back as HTTP 200 with an XML exception report.

Public, no credentials, CC BY 4.0. Sampling needs the ``raster`` extra
(``pip install effis-client[raster]``).
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Literal

from effis_client.errors import EffisError, describe

if TYPE_CHECKING:
    import httpx

WMS_URL = "https://maps.effis.emergency.copernicus.eu/effis"
Component = Literal["fwi", "ffmc", "dmc", "dc", "isi", "bui"]
COMPONENTS: tuple[Component, ...] = ("fwi", "ffmc", "dmc", "dc", "isi", "bui")

#: Pixel size of the requested raster, in degrees.
DEFAULT_STEP = 0.05

#: (west, south, east, north) in EPSG:4326 degrees.
BBox = tuple[float, float, float, float]
#: (lon, lat).
Point = tuple[float, float]


def fwi_params(
    day: date,
    bbox: BBox,
    *,
    component: Component = "fwi",
    step: float = DEFAULT_STEP,
) -> dict[str, str]:
    """Query parameters of the WMS GetMap request for one component and day.

    ``bbox`` is in the usual lon/lat order; WMS 1.3.0 with EPSG:4326 wants
    latitude first, and the swap happens here.
    """
    west, south, east, north = bbox
    return {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": f"mf010.{component}",
        "STYLES": "",
        "CRS": "EPSG:4326",
        "BBOX": f"{south},{west},{north},{east}",
        "WIDTH": str(round((east - west) / step)),
        "HEIGHT": str(round((north - south) / step)),
        "FORMAT": "image/tiff",
        "TIME": day.isoformat(),
    }


def sample_fwi(tiff: bytes, points: list[Point]) -> dict[Point, float] | None:
    """The pixel value under each point; ``None`` when the raster is all zeros.

    Points outside the raster, or on a non-finite pixel, are left out.
    """
    import numpy as np
    from rasterio.io import MemoryFile

    with MemoryFile(tiff) as mem, mem.open() as raster:
        values = raster.read(1)
        if not np.any(values):
            return None
        height, width = raster.height, raster.width
        out: dict[Point, float] = {}
        for lon, lat in points:
            row, col = raster.index(lon, lat)
            if 0 <= row < height and 0 <= col < width:
                v = float(values[row, col])
                if np.isfinite(v):
                    out[(lon, lat)] = v
        return out


def check_tiff(content_type: str, body: bytes) -> bytes:
    """Return ``body`` if it is a GeoTIFF, else raise :class:`EffisError`."""
    if not content_type.startswith("image/tiff"):
        raise EffisError(f"EFFIS WMS did not return a GeoTIFF: {describe(body)}")
    return body


async def fetch_fwi(
    client: httpx.AsyncClient,
    day: date,
    points: list[Point],
    bbox: BBox,
    *,
    component: Component = "fwi",
    step: float = DEFAULT_STEP,
    url: str = WMS_URL,
) -> dict[Point, float] | None:
    """One component of the EFFIS chain for ``day``, sampled at ``points``.

    ``None`` means EFFIS has no data for that day. Network and HTTP errors
    propagate; an XML error disguised as a 200 raises :class:`EffisError`.
    """
    response = await client.get(url, params=fwi_params(day, bbox, component=component, step=step))
    response.raise_for_status()
    tiff = check_tiff(response.headers.get("content-type", ""), response.content)
    return sample_fwi(tiff, points)
