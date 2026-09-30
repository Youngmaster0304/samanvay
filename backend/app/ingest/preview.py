"""Raster previews: where a GeoTIFF sits on the map, and what it looks like.

Two honest products of the stored bytes: the WGS 84 bounds the raster covers
(for placing it on the map) and an 8-bit RGB PNG rendering (for showing it).
Nothing here edits the registered file; float bands get a 2-98% stretch purely
for display, and the stretch never touches the stored data.
"""

from __future__ import annotations

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.warp import transform_bounds as warp_bounds

_MAX_PREVIEW_DIM = 1200


class PreviewError(Exception):
    """A preview cannot be produced; carries the API error code and message."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def bounds_wgs84(src: rasterio.DatasetReader) -> tuple[float, float, float, float]:
    if src.crs is None:
        raise PreviewError(
            "preview_needs_crs",
            "the raster carries no CRS, so it cannot be placed on the map",
        )
    west, south, east, north = warp_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21)
    return float(west), float(south), float(east), float(north)


def preview_info(data: bytes) -> dict[str, object]:
    """Read the raster header: WGS 84 bounds and native pixel size."""
    with MemoryFile(data) as memfile, memfile.open() as src:
        west, south, east, north = bounds_wgs84(src)
        return {
            "bounds": [west, south, east, north],
            "width": int(src.width),
            "height": int(src.height),
        }


def _to_uint8(band: np.ndarray) -> np.ndarray:
    """Display stretch for non-8-bit bands: 2-98 percentile window."""
    if band.dtype == np.uint8:
        return band
    lo, hi = np.nanpercentile(band, (2.0, 98.0))
    if not np.isfinite(lo):
        lo = 0.0
    if not np.isfinite(hi) or hi <= lo:
        hi = lo + 1.0
    filled = np.nan_to_num(band, nan=float(lo))
    scaled = np.clip((filled - lo) / (hi - lo), 0.0, 1.0)
    stretched: np.ndarray = scaled * 255.0
    return stretched.astype(np.uint8)


def preview_png(data: bytes, *, max_dim: int = _MAX_PREVIEW_DIM) -> bytes:
    """A downsampled RGB PNG of the raster, plus nothing else."""
    with MemoryFile(data) as memfile, memfile.open() as src:
        scale = min(1.0, max_dim / max(src.width, src.height))
        out_width = max(1, int(src.width * scale))
        out_height = max(1, int(src.height * scale))
        if src.count >= 3:
            stack = src.read(
                indexes=[1, 2, 3],
                out_shape=(3, out_height, out_width),
                resampling=Resampling.average,
            )
        else:
            gray = src.read(
                1,
                out_shape=(out_height, out_width),
                resampling=Resampling.average,
            )
            stack = np.stack([gray, gray, gray])
        rgb = np.stack([_to_uint8(stack[index]) for index in range(3)])

    with MemoryFile() as out:
        with out.open(
            driver="PNG",
            height=int(rgb.shape[1]),
            width=int(rgb.shape[2]),
            count=3,
            dtype="uint8",
        ) as dst:
            dst.write(rgb, indexes=[1, 2, 3])
        return bytes(out.getbuffer())
