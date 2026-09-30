"""Coordinate column detection for CSV uploads.

A GNSS export and a record-of-rights table are both CSVs; the difference is whether the
header names a coordinate pair. Detection is deliberately conservative: bare `x`/`y`
are not accepted, because a table column called `y` is more often a year than a
northing, and guessing here would silently invent geometry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

_NORMALISE = re.compile(r"[^a-z]")

_LAT_NAMES = frozenset({"lat", "latitude"})
_LON_NAMES = frozenset({"lon", "lng", "long", "longitude"})
_EAST_NAMES = frozenset({"east", "easting"})
_NORTH_NAMES = frozenset({"north", "northing"})

CoordinateKind = Literal["geographic", "projected"]


@dataclass(frozen=True)
class CoordinateColumns:
    """Which header columns hold coordinates, and in what system."""

    first: str
    second: str
    kind: CoordinateKind


def _norm(header: str) -> str:
    return _NORMALISE.sub("", header.strip().lower())


def find_coordinate_columns(headers: list[str]) -> CoordinateColumns | None:
    """Return the coordinate pair for `headers`, or None if it has none.

    Geographic pairs (latitude/longitude) imply WGS 84. Projected pairs
    (easting/northing) imply nothing at all, so the caller must demand a declared CRS.
    """
    for header in headers:
        normalised = _norm(header)
        if normalised in _EAST_NAMES or normalised.endswith("easting"):
            other = _find_pair(headers, _NORTH_NAMES, ("northing",))
            if other is not None:
                return CoordinateColumns(first=header, second=other, kind="projected")
    for header in headers:
        normalised = _norm(header)
        if normalised in _LAT_NAMES:
            other = _find_pair(headers, _LON_NAMES, ())
            if other is not None:
                return CoordinateColumns(first=header, second=other, kind="geographic")
    return None


def _find_pair(headers: list[str], exact: frozenset[str], contains: tuple[str, ...]) -> str | None:
    for header in headers:
        normalised = _norm(header)
        if normalised in exact or any(token in normalised for token in contains):
            return header
    return None


def parse_float(raw: str) -> float | None:
    """Parse a coordinate cell; None when it is blank or not a number.

    Deliberately strict: no thousands separators are stripped, because rewriting a
    cell before parsing it is how a coordinate gets invented.
    """
    text = raw.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
