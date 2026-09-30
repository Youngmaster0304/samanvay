"""GeoTIFF inspection, including whether the file is actually a COG.

The Cloud Optimized GeoTIFF check is structural (`base.assess_cog`), and its result is
reported rather than repaired: Stage 1 registers what arrived. Conversion to a COG is a
derived product with its own checksum, so it belongs with the tiling stage, not here.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.sources import SourceFormat
from app.ingest.connectors.base import Inspection, read_raster


def inspect_geotiff(path: Path) -> Inspection:
    """Read a GeoTIFF's metadata and report honestly whether it is a COG."""
    inspection = read_raster(path)
    raster = inspection.raster
    notes: list[str] = []
    if raster is not None and not raster.is_cog:
        failed = sorted(name for name, ok in raster.cog_checks.items() if not ok)
        notes.append(
            "not a Cloud Optimized GeoTIFF: " + ", ".join(failed) + " failed; "
            "windowed reads will read the whole strip"
        )

    return Inspection(
        format=SourceFormat.GEOTIFF,
        crs=inspection.crs,
        crs_hint=inspection.crs_hint,
        has_geometry=inspection.has_geometry,
        feature_count=inspection.feature_count,
        coverage=inspection.coverage,
        attributes=inspection.attributes,
        geometry_types=inspection.geometry_types,
        layer=inspection.layer,
        layers=inspection.layers,
        raster=inspection.raster,
        notes=notes,
    )
