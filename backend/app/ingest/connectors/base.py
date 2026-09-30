"""Connector results and the shared readers behind the per-format connectors.

Every connector answers the same question — what does this file actually contain? —
and reports only what GDAL/pyproj read back. Nothing here infers, fills or guesses.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyogrio
import rasterio
from rasterio.enums import Resampling

from app.domain.sources import CrsSource, SourceFormat
from app.ingest.gdal_guard import apply_gdal_limits

apply_gdal_limits()

_NO_GEOMETRY = "None"
_BLOCK_MULTIPLE = 16
_MAX_BLOCKSIZE = 4096


@dataclass(frozen=True)
class RasterInfo:
    driver: str
    width: int
    height: int
    bands: int
    dtypes: list[str]
    resolution: tuple[float, float]
    overviews: list[int]
    is_cog: bool
    cog_checks: dict[str, bool]


@dataclass(frozen=True)
class Inspection:
    format: SourceFormat
    crs: str | None
    crs_hint: CrsSource
    has_geometry: bool
    feature_count: int | None
    coverage: tuple[float, float, float, float] | None
    attributes: list[str]
    geometry_types: list[str]
    layer: str | None
    layers: list[str]
    raster: RasterInfo | None
    notes: list[str]


def _bounds_of(parts: list[float]) -> tuple[float, float, float, float] | None:
    if len(parts) != 4:
        return None
    if any(part != part for part in parts):  # NaN means "unknown extent"
        return None
    return (parts[0], parts[1], parts[2], parts[3])


def _layer_names(path: Path, layer: str | None) -> list[str]:
    if layer is not None:
        return [layer]
    try:
        rows = pyogrio.list_layers(str(path))
    except Exception:  # a single-file datasource with no layer list is still readable
        return [layer] if layer else []
    return [str(row[0]) for row in rows]


def read_vector(path: Path, *, layer: str | None = None) -> Inspection:
    """Inspect one vector layer with pyogrio, without loading its geometries."""
    with warnings.catch_warnings():
        # pyogrio says out loud what `_layer_names` reports as a note.
        warnings.filterwarnings("ignore", message="More than one layer found")
        info: dict[str, Any] = pyogrio.read_info(str(path), layer=layer, force_feature_count=True)

    raw_crs = info.get("crs")
    crs = str(raw_crs) if isinstance(raw_crs, str) and raw_crs.strip() else None

    raw_geometry_type = info.get("geometry_type")
    geometry_type = str(raw_geometry_type) if raw_geometry_type is not None else _NO_GEOMETRY
    has_geometry = geometry_type != _NO_GEOMETRY

    raw_fields = info.get("fields")
    attributes = [str(name) for name in raw_fields] if raw_fields is not None else []

    raw_features = info.get("features")
    feature_count = int(raw_features) if isinstance(raw_features, int | float) else None
    if feature_count is not None and feature_count < 0:
        feature_count = None

    raw_bounds = info.get("total_bounds")
    coverage_parts = [float(value) for value in raw_bounds] if raw_bounds is not None else []
    coverage = _bounds_of(coverage_parts) if has_geometry else None

    raw_name = info.get("layer_name")
    active_layer = str(raw_name) if isinstance(raw_name, str) and raw_name else layer

    return Inspection(
        format=SourceFormat.GEOJSON,  # replaced by the caller with the detected format
        crs=crs,
        crs_hint=CrsSource.FILE if crs else CrsSource.NONE,
        has_geometry=has_geometry,
        feature_count=feature_count,
        coverage=coverage,
        attributes=attributes,
        geometry_types=[geometry_type] if has_geometry else [],
        layer=active_layer,
        # The caller's request, not the layer GDAL happened to open: with no request the
        # full layer list is reported, so a multi-layer file is never described by one.
        layers=_layer_names(path, layer),
        raster=None,
        notes=[],
    )


def assess_cog(
    *,
    driver: str,
    width: int,
    height: int,
    tiled: bool,
    block_height: int,
    block_width: int,
    overviews: list[int],
) -> tuple[bool, dict[str, bool]]:
    """Structural checks against the Cloud Optimized GeoTIFF layout.

    This is a structural check, not GDAL's full validator: it reports the four layout
    properties that matter for windowed reads, and says so.
    """
    checks = {
        "driver_gtiff": driver == "GTiff",
        "tiled": tiled,
        "blocksize_allowed": (
            block_width >= _BLOCK_MULTIPLE
            and block_height >= _BLOCK_MULTIPLE
            and block_width <= _MAX_BLOCKSIZE
            and block_height <= _MAX_BLOCKSIZE
            and block_width % _BLOCK_MULTIPLE == 0
            and block_height % _BLOCK_MULTIPLE == 0
        ),
        "overviews_present": bool(overviews)
        or min(width, height) <= max(block_width, block_height),
    }
    return all(checks.values()), checks


def read_raster(path: Path) -> Inspection:
    """Inspect a GeoTIFF with rasterio, without reading its pixels."""
    with rasterio.open(path) as src:
        driver = str(src.driver)
        width = int(src.width)
        height = int(src.height)
        bands = int(src.count)
        dtypes = [str(dtype) for dtype in src.dtypes]
        crs = str(src.crs) if src.crs is not None else None
        bounds = src.bounds
        coverage = _bounds_of(
            [float(bounds.left), float(bounds.bottom), float(bounds.right), float(bounds.top)]
        )
        res = src.res
        resolution = (float(res[0]), float(res[1]))
        block_shapes = src.block_shapes
        first_block = block_shapes[0] if block_shapes else (height, width)
        block_height, block_width = int(first_block[0]), int(first_block[1])
        # GDAL reports the layout through IMAGE_STRUCTURE; rasterio's `is_tiled`
        # property is deprecated and would be removed under our feet.
        structure = src.tags(ns="IMAGE_STRUCTURE") or {}
        tiled = structure.get("TILED", "NO").upper() == "YES"
        overviews = [int(level) for level in src.overviews(1)] if bands else []

    is_cog, cog_checks = assess_cog(
        driver=driver,
        width=width,
        height=height,
        tiled=tiled,
        block_height=block_height,
        block_width=block_width,
        overviews=overviews,
    )

    return Inspection(
        format=SourceFormat.GEOTIFF,
        crs=crs,
        crs_hint=CrsSource.FILE if crs else CrsSource.NONE,
        has_geometry=True,
        feature_count=None,
        coverage=coverage,
        attributes=[],
        geometry_types=[],
        layer=None,
        layers=[],
        raster=RasterInfo(
            driver=driver,
            width=width,
            height=height,
            bands=bands,
            dtypes=dtypes,
            resolution=resolution,
            overviews=overviews,
            is_cog=is_cog,
            cog_checks=cog_checks,
        ),
        notes=[],
    )


def read_csv_rows(path: Path) -> tuple[list[str], list[list[str]], str]:
    """Read a CSV with the standard library: header, data rows and the encoding used.

    UTF-8 first (with BOM), then cp1252. The encoding actually used is returned so it
    can be recorded rather than assumed.
    """
    import csv

    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(path, newline="", encoding=encoding) as handle:
                reader = csv.reader(handle)
                rows = list(reader)
        except UnicodeDecodeError:
            continue
        if not rows:
            raise ValueError("the CSV has no rows")
        header = [cell.strip() for cell in rows[0]]
        return header, [row for row in rows[1:] if any(cell.strip() for cell in row)], encoding
    raise ValueError("the CSV could not be decoded as UTF-8 or cp1252")


__all__ = [
    "Inspection",
    "RasterInfo",
    "assess_cog",
    "read_csv_rows",
    "read_raster",
    "read_vector",
]

# Re-exported so connectors can build overviews the same way the COG connector does.
_ = Resampling
