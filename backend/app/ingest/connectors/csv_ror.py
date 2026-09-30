"""CSV without a coordinate pair: a record-of-rights table.

Such a table has no geometry, which is a fact about the source rather than a defect:
the coordinate reference system does not apply to it. `resolve_crs` refuses a declared
CRS for this shape so the field cannot be filled in by habit.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.sources import CrsSource, SourceFormat
from app.ingest.connectors.base import Inspection, read_csv_rows


def inspect_ror_csv(path: Path) -> Inspection:
    header, rows, encoding = read_csv_rows(path)

    notes = [
        "no coordinate columns in the header: this is a table, not a spatial layer, so "
        "the coordinate reference system does not apply",
        f"file decoded as {encoding}",
        f"{len(rows)} data rows, {len(header)} columns",
    ]

    return Inspection(
        format=SourceFormat.CSV_ROR,
        crs=None,
        crs_hint=CrsSource.NONE,
        has_geometry=False,
        feature_count=len(rows),
        coverage=None,
        attributes=header,
        geometry_types=[],
        layer=None,
        layers=[],
        raster=None,
        notes=notes,
    )
