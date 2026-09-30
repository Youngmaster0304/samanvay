"""GeoPackage inspection.

A GeoPackage is a container: one file, usually several layers. Stage 1 registers the
file and records which layer was inspected; the API accepts a `layer` field when the
operator wants a specific one.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.sources import SourceFormat
from app.ingest.connectors.base import Inspection, read_vector


def inspect_gpkg(path: Path, *, layer: str | None = None) -> Inspection:
    inspection = read_vector(path, layer=layer)
    notes: list[str] = []

    if len(inspection.layers) > 1:
        notes.append(
            f"{len(inspection.layers)} layers in this file; inspected "
            f"{inspection.layer!r}. Others are stored but not described here"
        )

    return Inspection(
        format=SourceFormat.GPKG,
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
