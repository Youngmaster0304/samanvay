"""CSV with a coordinate pair: a GNSS point export.

The file is read as a table first. Coordinates are parsed cell by cell, and only rows
whose pair parses *and* falls inside the range the column names promise become usable
points. Everything else is counted and reported; nothing is coerced, swapped or filled.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.sources import CrsSource, SourceFormat
from app.ingest.connectors.base import Inspection, read_csv_rows
from app.ingest.csv_columns import find_coordinate_columns, parse_float
from app.ingest.errors import IngestError

_WGS84 = "EPSG:4326"


def _in_range(kind: str, first: float, second: float) -> bool:
    if kind == "geographic":
        return -90.0 <= first <= 90.0 and -180.0 <= second <= 180.0
    return True


def inspect_gnss_csv(path: Path) -> Inspection:
    header, rows, encoding = read_csv_rows(path)
    coords = find_coordinate_columns(header)
    if coords is None:
        raise IngestError(
            "no_coordinate_columns",
            "this CSV has no coordinate pair in its header, so it is not a GNSS export",
        )

    first_index = header.index(coords.first)
    second_index = header.index(coords.second)

    usable = 0
    unparseable = 0
    out_of_range = 0
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    for row in rows:
        first = parse_float(row[first_index]) if first_index < len(row) else None
        second = parse_float(row[second_index]) if second_index < len(row) else None
        if first is None or second is None:
            unparseable += 1
            continue
        if not _in_range(coords.kind, first, second):
            out_of_range += 1
            continue

        if coords.kind == "geographic":
            x, y = second, first  # first is latitude, second is longitude
        else:
            x, y = first, second

        usable += 1
        min_x, max_x = min(min_x, x), max(max_x, x)
        min_y, max_y = min(min_y, y), max(max_y, y)

    if usable == 0:
        raise IngestError(
            "no_usable_coordinates",
            "no row in this CSV has a parseable coordinate pair inside the valid range "
            f"for its columns ({coords.first}, {coords.second})",
        )

    if coords.kind == "geographic":
        crs, crs_hint = _WGS84, CrsSource.IMPLICIT_WGS84
        assumption = (
            f"latitude/longitude columns ({coords.first}, {coords.second}) found; read as "
            "WGS 84 (EPSG:4326), which is what a lat/lon pair means by convention. "
            "Set declared_crs to record a different datum"
        )
    else:
        crs, crs_hint = None, CrsSource.NONE
        assumption = (
            f"easting/northing columns ({coords.first}, {coords.second}) found; a projected "
            "pair implies no CRS, so declared_crs is required"
        )

    notes = [assumption, f"file decoded as {encoding}"]
    if unparseable:
        notes.append(
            f"{unparseable} of {len(rows)} rows have a blank or non-numeric coordinate and "
            "were not counted as points"
        )
    if out_of_range:
        notes.append(
            f"{out_of_range} of {len(rows)} rows hold coordinates outside the valid range for "
            "their column names and were not counted as points"
        )

    return Inspection(
        format=SourceFormat.CSV_GNSS,
        crs=crs,
        crs_hint=crs_hint,
        has_geometry=True,
        feature_count=usable,
        coverage=(min_x, min_y, max_x, max_y),
        attributes=header,
        geometry_types=["Point"],
        layer=None,
        layers=[],
        raster=None,
        notes=notes,
    )
