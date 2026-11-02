"""Client for the public EFFIS services: burnt-area perimeters and official FWI rasters."""

from importlib.metadata import version

from effis_client.errors import EffisError
from effis_client.fwi import (
    COMPONENTS,
    WMS_URL,
    Component,
    check_tiff,
    fetch_fwi,
    fwi_params,
    sample_fwi,
)
from effis_client.perimeters import (
    DEFAULT_MAX_FEATURES,
    LAYER,
    WFS_URL,
    Perimeters,
    feature_date,
    fetch_perimeters,
    parse_perimeters,
    perimeters_params,
)

__version__ = version("effis-client")

__all__ = [
    "COMPONENTS",
    "DEFAULT_MAX_FEATURES",
    "LAYER",
    "WFS_URL",
    "WMS_URL",
    "Component",
    "EffisError",
    "Perimeters",
    "__version__",
    "check_tiff",
    "feature_date",
    "fetch_fwi",
    "fetch_perimeters",
    "fwi_params",
    "parse_perimeters",
    "perimeters_params",
    "sample_fwi",
]
