"""Fetch the real Copernicus DEM GLO-30 elevation tile covering Sector 22.

    uv run python scripts/fetch_terrain_dsm.py             # build (reuses cached GeoTIFF)
    uv run python scripts/fetch_terrain_dsm.py --refetch   # re-read the COG from AWS
    SAMANVAY_API=https://samanvay-api-wjkk.onrender.com \
        uv run python scripts/fetch_terrain_dsm.py --register

Data: Copernicus DEM GLO-30 (© ESA / DLR, based on TanDEM-X, free use with
attribution), a public 30 m COG on S3, window-read with rasterio's /vsicurl so
only the bbox is downloaded. The file keeps the COG's native EPSG:4326 grid;
the ingest reprojects coverage to storage SRID 32643 itself. Values are real
elevation in metres (float32).
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
import rasterio
from demo_drone_flight import post_bytes
from rasterio import Env
from rasterio.io import MemoryFile
from rasterio.windows import Window, from_bounds

# 1-by-1-degree GLO-30 tile containing the bbox (76.76-76.78 E, 30.72-30.74 N).
DEM_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_N30_00_E076_00_DEM/"
    "Copernicus_DSM_COG_10_N30_00_E076_00_DEM.tif"
)
BBOX_WGS84 = (76.7629635, 30.7263491, 76.7797155, 30.7397398)  # west, south, east, north
API = os.environ.get("SAMANVAY_API", "http://localhost:8000")
OUT = Path(__file__).resolve().parents[1] / "data" / "satellite" / "sector22_glo30_dsm.tif"
NAME = "Copernicus DEM GLO-30 (Sector 22)"
LICENCE = "Copernicus DEM (© DLR / ESA, free use with attribution)"
AUTHORITY = "ESA / DLR Copernicus DEM (TanDEM-X)"


def build() -> None:
    west, south, east, north = BBOX_WGS84
    env = Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        AWS_NO_SIGN_REQUEST="TRUE",
        GDAL_HTTP_TIMEOUT="60",
    )
    with env, rasterio.open(DEM_URL) as src:
        print(f"source grid {src.width}x{src.height} {src.dtypes[0]} crs={src.crs}")
        fractional = from_bounds(west, south, east, north, transform=src.transform)
        col = max(0, math.floor(fractional.col_off))
        row = max(0, math.floor(fractional.row_off))
        width = min(math.ceil(fractional.col_off + fractional.width) - col, src.width - col)
        height = min(math.ceil(fractional.row_off + fractional.height) - row, src.height - row)
        window = Window(col_off=col, row_off=row, width=width, height=height)
        elevation = src.read(1, window=window)
        transform = src.window_transform(window)
        crs = src.crs
        nodata = src.nodata
    valid = elevation[np.isfinite(elevation)]
    if nodata is not None:
        valid = valid[valid != nodata]
    print(
        f"window {elevation.shape[1]}x{elevation.shape[0]} px, "
        f"elevation {valid.min():.1f} to {valid.max():.1f} m"
    )
    profile = {
        "driver": "GTiff",
        "height": elevation.shape[0],
        "width": elevation.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "compress": "deflate",
    }
    memory = MemoryFile()
    with memory.open(**profile) as dataset:
        dataset.write(elevation.astype("float32"), 1)
    payload = memory.read()
    memory.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(payload)
    print(f"saved {len(payload)} bytes to {OUT}")


def register() -> str:
    return post_bytes(
        OUT.read_bytes(),
        filename="sector22_glo30_dsm.tif",
        kind="dsm",
        name=NAME,
        extra={
            "licence": LICENCE,
            "authority": AUTHORITY,
            "url": DEM_URL,
            "vintage": "2015-12-31",
            "is_synthetic": "false",
        },
    )


def main() -> None:
    if "--refetch" in sys.argv or not OUT.exists():
        build()
    else:
        print(f"reusing {OUT} (pass --refetch to re-read the COG from AWS)")

    if "--register" in sys.argv:
        source_id = register()
        print(f"registered real source {source_id}")


if __name__ == "__main__":
    main()
