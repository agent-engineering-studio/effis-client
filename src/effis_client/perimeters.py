"""Burnt-area perimeters from the EFFIS WFS.

The endpoint is **MapServer**, not GeoServer, and that shapes every choice
below. Verified against the live service:

* the base path is ``/gwis``, not ``/gwis/ows`` -- the latter hangs;
* the layer is ``nrt.ba.poly``. A layer that does not exist makes MapServer
  close the connection mid-response, which surfaces as a transport error
  rather than a 404;
* ``CQL_FILTER`` is a GeoServer vendor parameter. MapServer ignores it, so a
  date range expressed that way silently filters nothing;
* ``bbox`` and ``filter`` are mutually exclusive in WFS (and combining them
  kills the connection), so the bbox goes on the wire and the dates are
  applied locally. Cheap in practice: one Italian region's whole history is
  a single response -- Basilicata is 515 perimeters across 2012-2026, 305 KB;
* parameter names are lowercase: MapServer's WFS 1.1.0 does not accept the
  camelCase spellings GeoServer tolerates.

No credentials are needed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from effis_client.errors import EffisError, describe

if TYPE_CHECKING:
    import httpx

WFS_URL = "https://maps.effis.emergency.copernicus.eu/gwis"
LAYER = "nrt.ba.poly"

#: Server-side cap. Above the largest single-region history measured, so the
#: local date filter never sees a truncated set.
DEFAULT_MAX_FEATURES = 5000

#: (west, south, east, north) in EPSG:4326 degrees.
BBox = tuple[float, float, float, float]

_DATE_FIELDS = ("initialdate", "firedate", "FIREDATE", "fire_date")


@dataclass(frozen=True, slots=True)
class Perimeters:
    """The perimeters in the requested window, and how many came back in all.

    ``truncated`` is true when the server returned exactly its cap: the
    local date filter then worked on a partial set, and a gap would read as
    "no fires that season". Raise ``max_features`` or shrink the bbox.
    """

    features: list[dict[str, Any]]
    fetched: int
    truncated: bool


def perimeters_params(
    bbox: BBox,
    *,
    layer: str = LAYER,
    max_features: int = DEFAULT_MAX_FEATURES,
) -> dict[str, str]:
    """Query parameters of the WFS GetFeature request for ``bbox``."""
    west, south, east, north = bbox
    return {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typename": layer,
        "outputformat": "geojson",
        "srsname": "EPSG:4326",
        "bbox": f"{west},{south},{east},{north}",
        "maxfeatures": str(max_features),
    }


def feature_date(feature: dict[str, Any]) -> date | None:
    """The day a fire started, from whichever field the layer carries."""
    props = feature.get("properties") or {}
    if not isinstance(props, dict):
        return None
    for key in _DATE_FIELDS:
        raw = props.get(key)
        if raw:
            try:
                return date.fromisoformat(str(raw)[:10])
            except ValueError:
                return None
    return None


def parse_perimeters(
    content: bytes | str,
    *,
    start: date,
    end: date,
    max_features: int = DEFAULT_MAX_FEATURES,
) -> Perimeters:
    """Parse a GetFeature response and keep the fires started in ``[start, end]``.

    A feature with no readable date is **kept**: dropping it would lose a
    perimeter that is still real. An empty body is an empty result.

    Raises :class:`EffisError` when the body is not a GeoJSON
    FeatureCollection -- MapServer answers 200 with an XML exception report.
    """
    if not content:
        return Perimeters(features=[], fetched=0, truncated=False)
    try:
        payload = json.loads(content)
    except ValueError as exc:
        raise EffisError(f"EFFIS WFS did not return GeoJSON: {describe(content)}") from exc
    features = (payload.get("features") or []) if isinstance(payload, dict) else None
    if not isinstance(features, list) or not all(_is_feature(f) for f in features):
        raise EffisError(f"EFFIS WFS did not return a FeatureCollection: {describe(content)}")
    in_window = [f for f in features if _within(f, start, end)]
    return Perimeters(
        features=in_window,
        fetched=len(features),
        truncated=len(features) >= max_features,
    )


async def fetch_perimeters(
    client: httpx.AsyncClient,
    bbox: BBox,
    *,
    start: date,
    end: date,
    url: str = WFS_URL,
    layer: str = LAYER,
    max_features: int = DEFAULT_MAX_FEATURES,
) -> Perimeters:
    """Fetch the burnt-area perimeters intersecting ``bbox``, started in ``[start, end]``.

    Network and HTTP errors propagate (``httpx.HTTPError``); retries and
    timeouts are the caller's, through ``client``.
    """
    response = await client.get(
        url, params=perimeters_params(bbox, layer=layer, max_features=max_features)
    )
    response.raise_for_status()
    if response.status_code == 204:
        return Perimeters(features=[], fetched=0, truncated=False)
    return parse_perimeters(response.content, start=start, end=end, max_features=max_features)


def _is_feature(feature: Any) -> bool:
    return isinstance(feature, dict) and isinstance(feature.get("properties") or {}, dict)


def _within(feature: dict[str, Any], start: date, end: date) -> bool:
    when = feature_date(feature)
    return when is None or start <= when <= end
