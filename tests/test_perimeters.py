"""Perimeters: the request MapServer accepts, and the local date window.

The fixture is a real response of the EFFIS WFS (2026-11-02, a small bbox
around Matera), trimmed to three perimeters: 2012, 2021 and 2026.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import httpx
import pytest

from effis_client import (
    DEFAULT_MAX_FEATURES,
    LAYER,
    WFS_URL,
    EffisError,
    feature_date,
    fetch_perimeters,
    parse_perimeters,
    perimeters_params,
)

FIXTURES = Path(__file__).parent / "fixtures"
BODY = (FIXTURES / "perimeters.geojson").read_bytes()
BBOX = (16.5, 40.3, 16.8, 40.6)


def test_the_service_is_mapserver_at_gwis() -> None:
    """`/gwis/ows` hangs, and `effis:ba.fires` does not exist."""
    assert WFS_URL.endswith("/gwis")
    assert LAYER == "nrt.ba.poly"


def test_params_are_lowercase_with_bbox_and_no_filter() -> None:
    """MapServer's WFS 1.1.0 refuses camelCase, ignores CQL_FILTER, and
    drops the connection when bbox and filter are combined."""
    params = perimeters_params(BBOX)
    assert params["typename"] == "nrt.ba.poly"
    assert params["outputformat"] == "geojson"
    assert params["bbox"] == "16.5,40.3,16.8,40.6"
    assert params["maxfeatures"] == str(DEFAULT_MAX_FEATURES)
    assert all(k == k.lower() for k in params)
    assert "filter" not in params
    assert "CQL_FILTER" not in params


def test_the_date_window_is_applied_locally_and_inclusive() -> None:
    out = parse_perimeters(BODY, start=date(2021, 8, 13), end=date(2026, 12, 31))
    assert out.fetched == 3
    assert [feature_date(f) for f in out.features] == [date(2021, 8, 13), date(2026, 10, 3)]
    assert not out.truncated


def test_a_feature_without_a_date_is_kept() -> None:
    """Dropping it would lose a perimeter that is still real."""
    body = b'{"features": [{"properties": {"id": "1"}, "geometry": null}]}'
    out = parse_perimeters(body, start=date(2024, 1, 1), end=date(2024, 12, 31))
    assert len(out.features) == 1


@pytest.mark.parametrize(
    ("props", "expected"),
    [
        ({"initialdate": "2022-08-03 12:29:00"}, date(2022, 8, 3)),
        ({"firedate": "2019-07-01"}, date(2019, 7, 1)),
        ({"FIREDATE": "2018-06-30T00:00:00"}, date(2018, 6, 30)),
        ({"initialdate": "not a date"}, None),
        ({}, None),
    ],
)
def test_feature_date_reads_every_known_field(props: dict[str, str], expected: date | None) -> None:
    assert feature_date({"properties": props}) == expected


def test_a_response_at_the_cap_is_flagged_truncated() -> None:
    """At the cap the date filter saw a partial set: a gap would read as a
    quiet season."""
    out = parse_perimeters(BODY, start=date(2000, 1, 1), end=date(2030, 1, 1), max_features=3)
    assert out.truncated


def test_an_empty_body_is_an_empty_result() -> None:
    out = parse_perimeters(b"", start=date(2024, 1, 1), end=date(2024, 12, 31))
    assert out.features == [] and out.fetched == 0


def test_an_xml_error_disguised_as_200_raises() -> None:
    xml = (FIXTURES / "layer_not_defined.xml").read_bytes()
    with pytest.raises(EffisError, match="did not return GeoJSON: LayerNotDefined"):
        parse_perimeters(xml, start=date(2024, 1, 1), end=date(2024, 12, 31))


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


def test_fetch_sends_the_params_and_filters() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=BODY)

    async def run() -> int:
        async with _client(httpx.MockTransport(handler)) as client:
            out = await fetch_perimeters(
                client, BBOX, start=date(2026, 1, 1), end=date(2026, 12, 31)
            )
        return len(out.features)

    assert asyncio.run(run()) == 1
    assert seen[0].url.path == "/gwis"
    assert seen[0].url.params["typename"] == "nrt.ba.poly"


def test_fetch_treats_204_as_empty() -> None:
    async def run() -> int:
        transport = httpx.MockTransport(lambda _: httpx.Response(204))
        async with _client(transport) as client:
            out = await fetch_perimeters(
                client, BBOX, start=date(2026, 1, 1), end=date(2026, 12, 31)
            )
        return out.fetched

    assert asyncio.run(run()) == 0


def test_fetch_lets_http_errors_propagate() -> None:
    """Retry and degradation policy belong to the caller."""

    async def run() -> None:
        transport = httpx.MockTransport(lambda _: httpx.Response(503))
        async with _client(transport) as client:
            await fetch_perimeters(client, BBOX, start=date(2026, 1, 1), end=date(2026, 12, 31))

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(run())


def test_a_non_xml_body_is_quoted() -> None:
    with pytest.raises(EffisError, match="'<html>"):
        parse_perimeters(b"<html>busy</html>", start=date(2024, 1, 1), end=date(2024, 12, 31))
