"""QC flags computed from the stored geometry alone (plan Stage 3).

No model output and no assumption about what a feature should be: each flag is a
measurement the geometry itself supports after it reaches the storage CRS.
Flags are stored per feature in `source_feature.qc_flags` and summarised by
`GET /sources/{id}/health`. Thresholds live in the `qc:` policy block.

Flag vocabulary (stable tokens so counts aggregate):

- `invalid_geometry`     — GEOS says the geometry is not OGC-valid (self-intersection,
                           ring errors); the exact reason is recoverable from the stored
                           geometry by running `explain_validity` on it again.
- `ring_fewer_than_4_points` — a polygon ring with fewer than 4 coordinates including
                           the closing point: a degenerate outline.
- `sliver_area`          — polygon area below `qc.min_polygon_area_m2`.
- `duplicate_vertex`     — consecutive identical coordinates in a ring, the signature
                           of sloppy CAD export.

Lines and points only ever receive `invalid_geometry`; the polygon checks do not
apply to them.
"""

from __future__ import annotations

from typing import Any

from shapely.geometry.base import BaseGeometry

from app.core.policy import PolicyBundle
from app.ingest.errors import IngestError


def qc_limits(policy: PolicyBundle) -> dict[str, float]:
    block = policy.data.get("qc")
    if not isinstance(block, dict):
        raise IngestError("bad_policy", f"the policy must define a 'qc:' mapping in {policy.path}")
    value = block.get("min_polygon_area_m2")
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise IngestError("bad_policy", "policy 'qc.min_polygon_area_m2' must be a positive number")
    return {"min_polygon_area_m2": float(value)}


def _rings(polygon: Any) -> list[list[tuple[float, float]]]:
    rings = [list(polygon.exterior.coords)]
    rings.extend(list(interior.coords) for interior in polygon.interiors)
    return rings


def _polygon_flags(geom: Any, limits: dict[str, float]) -> list[str]:
    flags: list[str] = []
    polygons = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
    for polygon in polygons:
        if polygon.geom_type != "Polygon" or polygon.is_empty:
            continue
        if polygon.area < limits["min_polygon_area_m2"]:
            flags.append("sliver_area")
        for ring in _rings(polygon):
            closed = ring[:-1]  # the closing repeat is not a duplicate vertex
            if len(closed) < 3:
                flags.append("ring_fewer_than_4_points")
            for index in range(len(closed) - 1):
                if closed[index] == closed[index + 1]:
                    flags.append("duplicate_vertex")
                    break
    return flags


def qc_flags_for(geom: BaseGeometry, *, limits: dict[str, float]) -> list[str]:
    """Return the QC flag tokens for one geometry, deduplicated and stable-ordered."""
    flags: list[str] = []
    if not geom.is_valid:
        flags.append("invalid_geometry")
    if "Polygon" in geom.geom_type:
        flags.extend(_polygon_flags(geom, limits))
    # One token per kind even when several rings repeat the same defect.
    return list(dict.fromkeys(flags))
