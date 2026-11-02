# effis-client

Async Python client for the public services of
[EFFIS](https://forest-fire.emergency.copernicus.eu/), the European Forest
Fire Information System (Copernicus Emergency Management Service):

- **burnt-area perimeters**, from the WFS (`nrt.ba.poly`);
- the **official Fire Weather Index** chain (FWI, FFMC, DMC, DC, ISI, BUI) as
  raw float values from the WMS, sampled at any point.

No account and no API key: both services are public.

[![ci](https://github.com/agent-engineering-studio/effis-client/actions/workflows/ci.yml/badge.svg)](https://github.com/agent-engineering-studio/effis-client/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/effis-client)](https://pypi.org/project/effis-client/)

## Why a library for two HTTP calls

Because the EFFIS endpoints are **MapServer**, not GeoServer, and every
GeoServer habit fails differently — usually without an error:

| You try | What happens |
|---|---|
| `/gwis/ows` | the request hangs (use `/gwis`) |
| a wrong `typeName` | the connection closes mid-response, no 404 |
| `CQL_FILTER` for dates | silently ignored: you get every fire ever |
| `bbox` + `filter` together | the connection dies |
| camelCase WFS parameters | refused by MapServer's WFS 1.1.0 |
| `ecmwf007.fwi` (the layer in the EFFIS docs) | `LayerNotDefined` |
| any error | HTTP **200** with an XML body |
| FWI for a day past the forecast | HTTP 200 with a raster of **zeros** |

The last one is the dangerous one: an all-zero FWI raster reads as "no fire
danger anywhere" when it means "no data". This library returns `None` for
it. Each of these was found the hard way, and checked again against the live
service on 2 November 2026.

## Install

```bash
pip install effis-client           # perimeters
pip install "effis-client[raster]" # + FWI sampling (numpy, rasterio)
```

## Use

The fetch functions take your `httpx.AsyncClient`, so timeouts, retries,
proxies and connection pooling stay yours. Network errors propagate; an
error disguised as a 200 raises `EffisError`.

```python
import asyncio
from datetime import date

import httpx

from effis_client import fetch_fwi, fetch_perimeters


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        # Bounding boxes are (west, south, east, north), EPSG:4326.
        perimeters = await fetch_perimeters(
            client,
            (16.5, 40.3, 16.8, 40.6),
            start=date(2021, 1, 1),
            end=date(2026, 12, 31),
        )
        print(len(perimeters.features), "fires since 2021")

        fwi = await fetch_fwi(
            client,
            date(2026, 11, 1),
            points=[(16.6, 40.6)],  # (lon, lat)
            bbox=(15.0, 39.5, 17.5, 41.5),
        )
        print(fwi)  # {(16.6, 40.6): 10.34...} — or None if EFFIS has no data


asyncio.run(main())
```

Dates are filtered locally, because MapServer cannot filter them server
side; one bbox returns the whole history (an Italian region is a few hundred
perimeters, a few hundred KB). If the response hits `max_features`,
`perimeters.truncated` is `True`: shrink the bbox rather than trusting the
gap.

### Bring your own HTTP

Everything the fetch functions do is also exposed as pure functions, for
callers with their own HTTP layer:

```python
from effis_client import WFS_URL, perimeters_params, parse_perimeters
from effis_client import WMS_URL, fwi_params, check_tiff, sample_fwi
```

## Data licence

EFFIS data are © European Union, Copernicus Emergency Management Service,
published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Anything you publish from them must say so. The test fixtures are small
EFFIS responses under the same licence.

Extracted from [Limen](https://github.com/agent-engineering-studio/limen),
which uses the perimeters as the truth set for its wildfire backtest and the
FWI rasters to check its own FWI chain
([`fwi-chain`](https://github.com/agent-engineering-studio/fwi-chain)).

## Development

```bash
uv sync
make check
```

## License

Code: [Apache-2.0](./LICENSE).
