"""Shapefile inspection, including which sidecars arrived with the .shp.

A shapefile is five files wearing one extension. The sidecars that are missing change
what the source can be used for, so each gap is reported as a note instead of being
silently tolerated.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.sources import SourceFormat
from app.ingest.connectors.base import Inspection, read_vector

_SIDECARS = {
    ".dbf": "attribute table (.dbf)",
    ".shx": "shape index (.shx)",
    ".prj": "coordinate reference system (.prj)",
}


def inspect_shapefile(path: Path, *, layer: str | None = None) -> Inspection:
    inspection = read_vector(path, layer=layer)
    notes: list[str] = []

    for suffix, description in _SIDECARS.items():
        if not path.with_suffix(suffix).is_file():
            if suffix == ".prj":
                notes.append(
                    f"no {description} sidecar: the shapefile carries no coordinate "
                    "reference system, so declared_crs is required"
                )
            elif suffix == ".shx":
                notes.append(f"no {description} sidecar: GDAL rebuilt the index while reading")
            else:
                notes.append(f"no {description} sidecar: attributes are unavailable")

    return Inspection(
        format=SourceFormat.SHAPEFILE,
        crs=inspection.crs,
        crs_hint=inspection.crs_hint,
        has_geometry=inspection.has_geometry,
        feature_count=inspection.feature_count,
        coverage=inspection.coverage,
        attributes=inspection.attributes,
        geometry_types=inspection.geometry_types,
        layer=inspection.layer,
        layers=inspection.layers,
        raster=None,
        notes=[*notes, *inspection.notes],
    )
