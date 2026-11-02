"""Render the README figures from fetch_data.py output and the test fixtures.

Usage:
    uv run --with matplotlib python docs/scripts/render_images.py \
        <data-dir> docs/images tests/fixtures
"""

import collections
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import rasterio

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon

INK, MUTED, GRID, SEA = "#1f2328", "#59636e", "#d0d7de", "#eef2f6"
CREDIT = "Data © European Union, Copernicus EMS \u2013 EFFIS (CC BY 4.0)"
NAMES = {
    "fwi": "FWI — Fire Weather Index",
    "ffmc": "FFMC — Fine Fuel Moisture",
    "dmc": "DMC — Duff Moisture",
    "dc": "DC — Drought Code",
    "isi": "ISI — Initial Spread",
    "bui": "BUI — Buildup Index",
}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.titlecolor": INK,
        "axes.titleweight": "bold",
        "axes.titlesize": 12,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.dpi": 150,
    }
)


def read(path: Path) -> tuple[np.ndarray, list[float]]:
    with rasterio.open(path) as raster:
        b = raster.bounds
        return raster.read(1).astype(float), [b.left, b.right, b.bottom, b.top]


def land_cmap() -> Any:
    cmap = plt.get_cmap("YlOrRd").copy()
    cmap.set_bad(SEA)
    return cmap


def caption(fig: Any, text: str) -> None:
    fig.text(0.01, 0.01, text, color=MUTED, fontsize=7)


def fwi_italy(data: Path, out: Path) -> None:
    values, extent = read(data / "italy_fwi.tif")
    fig, ax = plt.subplots(figsize=(8, 7))
    image = ax.imshow(
        np.ma.masked_where(values <= 0, values),
        extent=extent,
        cmap=land_cmap(),
        vmin=0,
        vmax=50,
        interpolation="nearest",
    )
    ax.set_title("Official EFFIS Fire Weather Index — 1 August 2026", loc="left")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    bar = fig.colorbar(image, ax=ax, shrink=0.75, extend="max")
    bar.set_label("FWI")
    bar.outline.set_visible(False)
    caption(
        fig, f"fetch_fwi(client, date(2026, 8, 1), points, bbox=(6, 36, 19, 47.5))  ·  {CREDIT}"
    )
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(out / "fwi-italy.png")
    plt.close(fig)


def fwi_components(data: Path, out: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.4))
    for ax, (component, name) in zip(axes.flat, NAMES.items(), strict=True):
        values, extent = read(data / f"italy_{component}.tif")
        image = ax.imshow(
            np.ma.masked_where(values <= 0, values),
            extent=extent,
            cmap=land_cmap(),
            vmin=0,
            vmax=np.nanpercentile(values[values > 0], 98),
            interpolation="nearest",
        )
        ax.set_title(name, fontsize=10, loc="left")
        ax.set_xticks([])
        ax.set_yticks([])
        bar = fig.colorbar(image, ax=ax, shrink=0.8)
        bar.outline.set_visible(False)
        bar.ax.tick_params(labelsize=7)
    fig.suptitle(
        "The full Canadian FWI chain from EFFIS, 1 August 2026 — one call per component",
        x=0.01,
        ha="left",
        fontweight="bold",
        color=INK,
    )
    caption(
        fig, f'fetch_fwi(..., component="ffmc" | "dmc" | "dc" | "isi" | "bui" | "fwi")  ·  {CREDIT}'
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    fig.savefig(out / "fwi-components.png")
    plt.close(fig)


def start_year(feature: dict[str, Any]) -> int:
    props = feature["properties"]
    return int(str(props.get("initialdate") or props.get("firedate"))[:4])


def perimeters_map(features: list[dict[str, Any]], out: Path) -> None:
    years = [start_year(f) for f in features]
    first, last = min(years), max(years)
    patches, values = [], []
    for feature, year in zip(features, years, strict=True):
        geometry = feature["geometry"]
        polygons = (
            [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        )
        for polygon in polygons:
            patches.append(Polygon(np.array(polygon[0]), closed=True))
            values.append(year)
    fig, ax = plt.subplots(figsize=(8, 6.6))
    collection = PatchCollection(patches, cmap="YlOrRd", edgecolor="#7a2e0e", linewidth=0.2)
    collection.set_array(np.array(values))
    collection.set_clim(first - 3, last)
    ax.add_collection(collection)
    ax.set_xlim(15.3, 16.9)
    ax.set_ylim(39.85, 41.15)
    ax.set_aspect(1 / np.cos(np.radians(40.5)))
    ax.grid(color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    ax.set_title(
        f"{len(features)} burnt-area perimeters, {first}\u2013{last} "
        "(Basilicata and surroundings, Italy)",
        loc="left",
    )
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    bar = fig.colorbar(collection, ax=ax, shrink=0.75)
    bar.set_label("fire start year")
    bar.outline.set_visible(False)
    bar.ax.set_ylim(first, last)
    caption(
        fig,
        f"fetch_perimeters(client, (15.3, 39.85, 16.9, 41.15), start=..., end=...)  ·  {CREDIT}",
    )
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(out / "perimeters-basilicata.png", bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def perimeters_per_year(features: list[dict[str, Any]], out: Path) -> None:
    area: collections.Counter[int] = collections.Counter()
    count: collections.Counter[int] = collections.Counter()
    for feature in features:
        year = start_year(feature)
        with contextlib.suppress(ValueError):
            area[year] += float(feature["properties"].get("area") or 0)
        count[year] += 1
    years = list(range(min(count), max(count) + 1))
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.bar(years, [area[y] for y in years], width=0.7, color="#d9480f")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.yaxis.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.set_xticks(years)
    ax.set_ylabel("burnt area (ha)")
    ax.set_title("Burnt area per year in the same bounding box", loc="left")
    top = max(years, key=lambda y: area[y])
    ax.annotate(
        f"{area[top]:,.0f} ha · {count[top]} fires",
        (top, area[top]),
        xytext=(0, 4),
        textcoords="offset points",
        ha="center",
        fontsize=8,
        color=INK,
    )
    caption(fig, CREDIT)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out / "perimeters-per-year.png")
    plt.close(fig)


def zero_raster_trap(fixtures: Path, out: Path) -> None:
    panels = [
        ("fwi_2026-11-01.tif", "1 Nov 2026 — real data", "sample_fwi(...) → {(16.6, 40.6): 10.34}"),
        (
            "fwi_no_data.tif",
            "Past the forecast horizon — HTTP 200, all zeros",
            "sample_fwi(...) → None",
        ),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
    for ax, (name, title, result) in zip(axes, panels, strict=True):
        values, extent = read(fixtures / name)
        ax.imshow(values, extent=extent, cmap="YlOrRd", vmin=0, vmax=25, interpolation="nearest")
        ax.plot(16.6, 40.6, marker="o", ms=8, mfc="none", mec=INK, mew=2)
        ax.set_title(title, loc="left", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel(result, family="DejaVu Sans Mono", color=INK, fontsize=9)
    fig.suptitle(
        "Same request, same status code: one is a value, the other is missing data",
        x=0.01,
        ha="left",
        fontweight="bold",
        color=INK,
    )
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    fig.savefig(out / "zero-raster-trap.png", bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def main(data: Path, out: Path, fixtures: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    features = json.loads((data / "basilicata.geojson").read_text())["features"]
    fwi_italy(data, out)
    fwi_components(data, out)
    perimeters_map(features, out)
    perimeters_per_year(features, out)
    zero_raster_trap(fixtures, out)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
