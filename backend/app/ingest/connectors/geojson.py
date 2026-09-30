"""GeoJSON inspection.

A GeoJSON document with no `crs` member is WGS 84 by RFC 7946, so a missing CRS here is
an implication of the format rather than missing information. It is recorded with
`CrsSource.IMPLICIT_WGS84` so the summary shows the CRS was assumed, not read.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.sources import CrsSource, SourceFormat
from app.ingest.connectors.base import Inspection, read_vector

_WGS84 = "EPSG:4326"


def inspect_geojson(path: Path, *, layer: str | None = None) -> Inspection:
    inspection = read_vector(path, layer=layer)
    notes: list[str] = []
    crs = inspection.crs
    crs_hint = inspection.crs_hint

    if crs is None:
        crs = _WGS84
        crs_hint = CrsSource.IMPLICIT_WGS84
        notes.append(
            "no crs member in the document; read as WGS 84 (EPSG:4326) per RFC 7946. "
            "Set declared_crs to override"
        )

    if not inspection.has_geometry:
        notes.append("no geometry in this document: properties only")

    return Inspection(
        format=SourceFormat.GEOJSON,
        crs=crs,
        crs_hint=crs_hint,
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
