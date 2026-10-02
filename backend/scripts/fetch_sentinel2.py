"""Fetch a real Sentinel-2 L2A true-colour crop over Sector 22 and register it.

    uv run python scripts/fetch_sentinel2.py               # build (reuses cached GeoTIFF)
    uv run python scripts/fetch_sentinel2.py --refetch     # pull fresh from Earth Search
    SAMANVAY_API=https://samanvay-api-wjkk.onrender.com \
        uv run python scripts/fetch_sentinel2.py --register

Data: ESA Copernicus Sentinel-2 L2A, searched through the Element84 Earth Search
STAC API (no auth) and window-read straight from the Sentinel COGs on AWS with
rasterio's /vsicurl, so only the ~1.6 km bbox is downloaded. Bands B04/B03/B02
(10 m) are contrast-stretched to 8-bit RGB for display; the output is a regular
GeoTIFF in the tile's native UTM zone (EPSG:32643). Sentinel data is free, full
and open with attribution.
"""

from __future__ import annotations

import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
from demo_drone_flight import post_bytes
from pyproj import Transformer
from rasterio import Env
from rasterio.io import MemoryFile
from rasterio.windows import Window, from_bounds

BBOX_WGS84 = (76.7629635, 30.7263491, 76.7797155, 30.7397398)  # west, south, east, north
EPSG = 32643
STAC = "https://earth-search.aws.element84.com/v1/search"
API = os.environ.get("SAMANVAY_API", "http://localhost:8000")
OUT = Path(__file__).resolve().parents[1] / "data" / "satellite" / "sector22_sentinel2.tif"
NAME = "Sentinel-2 L2A true colour (Sector 22)"
LICENCE = "Copernicus Sentinel data (free use with attribution)"
AUTHORITY = "ESA Copernicus Sentinel-2 via AWS (Element84 Earth Search)"
UA = {"User-Agent": "samanvay-sih2026/0.1"}


def search() -> dict:
    """Newest low-cloud Sentinel-2 L2A item covering the bbox (last 6 months)."""
    today = datetime.now(UTC)
    start = today - timedelta(days=180)
    params = urllib.parse.urlencode(
        {
            "collections": "sentinel-2-l2a",
            "bbox": ",".join(str(v) for v in BBOX_WGS84),
            "datetime": f"{start:%Y-%m-%d}T00:00:00Z/{today:%Y-%m-%d}T23:59:59Z",
            "limit": 40,
        }
    )
    request = urllib.request.Request(f"{STAC}?{params}", headers=UA)
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode())
    features = payload.get("features", [])
    if not features:
        raise SystemExit("Earth Search returned no Sentinel-2 scenes for the bbox")
    features.sort(key=lambda item: float(item["properties"].get("eo:cloud_cover", 100)))
    best = features[0]
    cloud = best["properties"].get("eo:cloud_cover")
    print(
        f"scene {best['id']}  date={best['properties']['datetime'][:10]}  "
        f"cloud={cloud if cloud is not None else '?'}%"
    )
    return best


def utm_bounds() -> tuple[float, float, float, float]:
    """WGS 84 bbox reprojected to EPSG:32643 (corners + edge midpoints)."""
    west, south, east, north = BBOX_WGS84
    points = [
        (west, south),
        (east, south),
        (east, north),
        (west, north),
        ((west + east) / 2, south),
        ((east + west) / 2, north),
        (west, (south + north) / 2),
        (east, (south + north) / 2),
    ]
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{EPSG}", always_xy=True)
    xs, ys = transformer.transform([p[0] for p in points], [p[1] for p in points])
    return min(xs), min(ys), max(xs), max(ys)


def _window(src, bounds: tuple[float, float, float, float]) -> Window:
    left, bottom, right, top = bounds
    fractional = from_bounds(left, bottom, right, top, transform=src.transform)
    col = max(0, math.floor(fractional.col_off))
    row = max(0, math.floor(fractional.row_off))
    width = math.ceil(fractional.col_off + fractional.width) - col
    height = math.ceil(fractional.row_off + fractional.height) - row
    width = min(width, src.width - col)
    height = min(height, src.height - row)
    return Window(col_off=col, row_off=row, width=width, height=height)


def _stretch(band: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(band.astype("float64"), [2, 98])
    if hi <= lo:
        hi = lo + 1.0
    scaled = np.clip((band.astype("float64") - lo) / (hi - lo), 0.0, 1.0)
    return (scaled * 255.0).round().astype("uint8")


def build(scene: dict) -> None:
    assets = scene["assets"]
    hrefs = [assets["red"]["href"], assets["green"]["href"], assets["blue"]["href"]]
    bounds = utm_bounds()
    env = Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        AWS_NO_SIGN_REQUEST="TRUE",
        GDAL_HTTP_TIMEOUT="60",
    )
    with env:
        arrays = []
        transform = None
        crs = None
        for href in hrefs:
            with rasterio.open(href) as src:
                window = _window(src, bounds)
                arrays.append(src.read(1, window=window))
                transform = src.window_transform(window)
                crs = src.crs
        assert transform is not None and crs is not None
    rgb = np.stack([_stretch(arrays[i]) for i in range(3)], axis=0)
    print(f"window {rgb.shape[2]}x{rgb.shape[1]} px, crs={crs}, nodata-free uint8 RGB")
    profile = {
        "driver": "GTiff",
        "height": rgb.shape[1],
        "width": rgb.shape[2],
        "count": 3,
        "dtype": "uint8",
        "crs": crs,
        "transform": transform,
        "compress": "deflate",
    }
    memory = MemoryFile()
    with memory.open(**profile) as dataset:
        dataset.write(rgb)
    payload = memory.read()
    memory.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(payload)
    print(f"saved {len(payload)} bytes to {OUT}")


def register(scene: dict) -> str:
    self_links = [link for link in scene.get("links", []) if link.get("rel") == "self"]
    source_url = self_links[0]["href"] if self_links else STAC
    vintage = scene["properties"]["datetime"][:10]
    return post_bytes(
        OUT.read_bytes(),
        filename="sector22_sentinel2.tif",
        kind="satellite",
        name=NAME,
        extra={
            "licence": LICENCE,
            "authority": AUTHORITY,
            "url": source_url,
            "vintage": vintage,
            "is_synthetic": "false",
        },
    )


def main() -> None:
    if "--refetch" in sys.argv or not OUT.exists():
        scene = search()
        build(scene)
    else:
        scene = None
        print(f"reusing {OUT} (pass --refetch to pull from Earth Search again)")

    if "--register" in sys.argv:
        if scene is None:
            scene = search()
        source_id = register(scene)
        print(f"registered real source {source_id}")


if __name__ == "__main__":
    main()
