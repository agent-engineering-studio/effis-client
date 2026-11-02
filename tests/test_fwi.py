"""Official FWI rasters: the WMS request and the sampling.

Fixtures are real EFFIS responses (2026-11-02, bbox 15.0-17.5 E,
39.5-41.5 N): the FWI of 2026-11-01, the all-zero raster served for a day
beyond the forecast, and the XML returned for a layer that does not exist.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import httpx
import pytest

from effis_client import (
    COMPONENTS,
    WMS_URL,
    EffisError,
    check_tiff,
    fetch_fwi,
    fwi_params,
    sample_fwi,
)

FIXTURES = Path(__file__).parent / "fixtures"
TIFF = (FIXTURES / "fwi_2026-11-01.tif").read_bytes()
NO_DATA = (FIXTURES / "fwi_no_data.tif").read_bytes()
XML = (FIXTURES / "layer_not_defined.xml").read_bytes()
BBOX = (15.0, 39.5, 17.5, 41.5)

MATERA = (16.6, 40.6)
SEA = (17.3, 39.7)


def test_the_service_is_effis_not_gwis() -> None:
    assert WMS_URL.endswith("/effis")


def test_params_swap_to_latitude_first_for_wms_130() -> None:
    """WMS 1.3.0 + EPSG:4326 is lat/lon; the caller speaks lon/lat."""
    params = fwi_params(date(2026, 11, 1), BBOX, component="dc")
    assert params["BBOX"] == "39.5,15.0,41.5,17.5"
    assert params["LAYERS"] == "mf010.dc"
    assert params["FORMAT"] == "image/tiff"
    assert params["TIME"] == "2026-11-01"
    assert (params["WIDTH"], params["HEIGHT"]) == ("50", "40")


def test_every_component_is_an_mf010_layer() -> None:
    """`ecmwf007.fwi`, the layer of the EFFIS example, answers LayerNotDefined."""
    assert COMPONENTS == ("fwi", "ffmc", "dmc", "dc", "isi", "bui")
    for c in COMPONENTS:
        assert fwi_params(date(2026, 11, 1), BBOX, component=c)["LAYERS"] == f"mf010.{c}"


def test_sampling_reads_the_pixel_under_each_point() -> None:
    out = sample_fwi(TIFF, [MATERA, SEA, (30.0, 45.0)])
    assert out is not None
    assert out[MATERA] == pytest.approx(10.343368530273438)
    # The sea is zero on a valid day too, and a single zero stays a value.
    assert out[SEA] == 0.0
    # Outside the raster: left out, not invented.
    assert (30.0, 45.0) not in out


def test_an_all_zero_raster_is_no_data_not_a_calm_day() -> None:
    assert sample_fwi(NO_DATA, [MATERA]) is None


def test_an_xml_error_disguised_as_200_raises() -> None:
    with pytest.raises(EffisError, match="LayerNotDefined"):
        check_tiff("text/xml; charset=UTF-8", XML)


def test_fetch_requests_and_samples() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, headers={"content-type": "image/tiff"}, content=TIFF)

    async def run() -> dict[tuple[float, float], float] | None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_fwi(client, date(2026, 11, 1), [MATERA], BBOX)

    out = asyncio.run(run())
    assert out is not None
    assert list(out) == [MATERA]
    assert out[MATERA] == pytest.approx(10.343368530273438)
    assert seen[0].url.path == "/effis"


def test_fetch_raises_on_the_xml_200() -> None:
    async def run() -> None:
        transport = httpx.MockTransport(
            lambda _: httpx.Response(200, headers={"content-type": "text/xml"}, content=XML)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            await fetch_fwi(client, date(2026, 11, 1), [MATERA], BBOX)

    with pytest.raises(EffisError):
        asyncio.run(run())
