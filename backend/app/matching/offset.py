"""Offset estimation between two loaded sources (backend.md 5.4).

Confident pairs (IoU >= 0.5 or centroid within the blocking radius) give a
displacement vector per pair — centroid(B) minus centroid(A). The estimate is
the median vector, outliers are rejected by the median absolute deviation, and
the median is re-estimated on the inliers. The result is reported in metres and
bearing; with `apply=True` the correction is written as a NEW observation (a
translated copy of B with a link to the original in `notes` and a
`transform_log` row) — the department's original row is never moved — and
matching is re-run against the corrected copy.

Honest limits: a single global translation (no rotation, no low-order field —
the Moran's I residual check arrives later), and the pair set is this slice's
radius blocking rather than a dedicated confident-pair query.
"""

from __future__ import annotations

import hashlib
import json
import math
from statistics import median
from typing import Any
from uuid import UUID

from pyproj import Transformer
from shapely.geometry import shape as shapely_shape
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.policy import PolicyBundle
from app.db.models import SourceRegistry, TransformLog
from app.ingest.errors import IngestError
from app.matching.service import (
    _NEAR,
    _NEAR_COUNT,
    _POLYGON_TYPES,
    _blocking_radius,
    _require_loaded,
    detect_matches,
    matching_limits,
)

_DERIVED_SUFFIX = " (offset-corrected)"


def _bearing_deg(dx: float, dy: float) -> float:
    """Compass bearing of the (east, north) vector: 0 = north, clockwise."""
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def _confident_vectors(
    session: Session,
    source_a: UUID,
    source_b: UUID,
    *,
    radius: float,
    max_pairs: float,
) -> tuple[list[tuple[float, float]], int]:
    """Displacement vectors (centroid_B - centroid_A) for confident pairs, and
    how many nearby pairs were examined to get them."""
    params = {"sa": source_a, "sb": source_b, "radius": radius}
    count = int(session.execute(_NEAR_COUNT, params).scalar_one())
    if count > max_pairs:
        raise IngestError(
            "too_many_pairs",
            f"{count} nearby pairs exceed matching.max_pairs={int(max_pairs)}; "
            "clip the sources to a smaller AOI",
        )
    vectors: list[tuple[float, float]] = []
    for row in session.execute(_NEAR, params).mappings().all():
        geometry_a = shapely_shape(json.loads(row["geom_a"]))
        geometry_b = shapely_shape(json.loads(row["geom_b"]))
        if geometry_a.geom_type not in _POLYGON_TYPES or geometry_b.geom_type not in _POLYGON_TYPES:
            continue
        centre_a = geometry_a.centroid
        centre_b = geometry_b.centroid
        distance = centre_a.distance(centre_b)
        union_area = geometry_a.union(geometry_b).area
        iou = (geometry_a.intersection(geometry_b).area / union_area) if union_area > 0 else 0.0
        if iou >= 0.5 or distance <= radius:
            vectors.append((float(centre_b.x - centre_a.x), float(centre_b.y - centre_a.y)))
    return vectors, count


def _robust_median(
    vectors: list[tuple[float, float]],
) -> tuple[float, float, list[tuple[float, float]], float, int]:
    """Median vector, MAD rejection, re-estimate. Returns (dx, dy, inliers, thresh, rejected)."""
    mdx = float(median(v[0] for v in vectors))
    mdy = float(median(v[1] for v in vectors))
    distances = [math.hypot(v[0] - mdx, v[1] - mdy) for v in vectors]
    med_d = float(median(distances))
    mad = float(median(abs(d - med_d) for d in distances))
    threshold = med_d + 3.0 * 1.4826 * mad
    inliers = [v for v, d in zip(vectors, distances, strict=True) if d <= threshold]
    rejected = len(vectors) - len(inliers)
    dx = float(median(v[0] for v in inliers))
    dy = float(median(v[1] for v in inliers))
    return dx, dy, inliers, threshold, rejected


def _translated_coverage(row_b: SourceRegistry, dx: float, dy: float) -> list[float] | None:
    """The coverage box after translating features by (dx, dy) in the storage CRS.

    `coverage` is kept in the file's own CRS, so the box is transformed to the
    storage CRS, moved, and transformed back — or moved directly when the file
    already lives in the storage CRS.
    """
    if row_b.coverage is None or len(row_b.coverage) != 4:
        return None
    storage = f"EPSG:{get_settings().storage_srid}"
    file_crs = row_b.crs_used or row_b.crs_original or storage
    west, south, east, north = row_b.coverage
    if file_crs.upper() == storage.upper():
        return [west + dx, south + dy, east + dx, north + dy]
    to_storage = Transformer.from_crs(file_crs, storage, always_xy=True)
    xs, ys = to_storage.transform([west, east], [south, north])
    xs = [xs[0] + dx, xs[1] + dx]
    ys = [ys[0] + dy, ys[1] + dy]
    back = Transformer.from_crs(storage, file_crs, always_xy=True)
    fx, fy = back.transform(xs, ys)
    return [float(min(fx)), float(min(fy)), float(max(fx)), float(max(fy))]


def _apply_correction(
    session: Session,
    row_b: SourceRegistry,
    *,
    dx: float,
    dy: float,
    pairs_used: int,
    pairs_total: int,
    rmse_m: float,
    max_resid_m: float,
    threshold: float,
    rejected: int,
) -> UUID:
    """Write the translated copy of B as a new observation (idempotent by name)."""
    derived_name = f"{row_b.name}{_DERIVED_SUFFIX}"
    derived = session.execute(
        select(SourceRegistry).where(SourceRegistry.name == derived_name)
    ).scalar_one_or_none()

    sha = hashlib.sha256(f"{row_b.sha256}|offset|{dx:.4f}|{dy:.4f}".encode()).hexdigest()
    note = (
        f"Derived from {row_b.name} ({row_b.source_id}) by a translation of "
        f"({dx:+.2f} m east, {dy:+.2f} m north), the median of {pairs_used} of "
        f"{pairs_total} matched centroid pairs after MAD rejection; "
        "the original source row is unchanged."
    )
    coverage = _translated_coverage(row_b, dx, dy)

    if derived is None:
        derived = SourceRegistry(
            name=derived_name,
            kind=row_b.kind,
            authority=row_b.authority,
            licence=row_b.licence,
            url=row_b.url,
            vintage=row_b.vintage,
            is_synthetic=row_b.is_synthetic,
            sigma_m=row_b.sigma_m,
            sha256=sha,
            size_bytes=row_b.size_bytes,
            object_key=row_b.object_key,
            client_key=None,
            format=row_b.format,
            crs_original=row_b.crs_original,
            crs_declared=row_b.crs_declared,
            crs_used=row_b.crs_used,
            crs_source=row_b.crs_source,
            has_geometry=row_b.has_geometry,
            feature_count=row_b.feature_count,
            coverage=coverage,
            attributes=row_b.attributes,
            geometry_types=row_b.geometry_types,
            layer=row_b.layer,
            layers=row_b.layers,
            raster=None,
            notes=[note],
        )
        session.add(derived)
        session.flush()
    else:
        derived.sha256 = sha
        derived.coverage = coverage
        derived.feature_count = row_b.feature_count
        derived.notes = [note]

    # Rebuild the copy from the original every time: re-running with the same
    # offset never shifts twice, and a new offset replaces the old correction.
    session.execute(
        text("DELETE FROM source_feature WHERE source_id = :derived"),
        {"derived": derived.source_id},
    )
    session.execute(
        text(
            """
            INSERT INTO source_feature
                (obs_id, source_id, source_fid, feature_class, geom,
                 raw_props, extractor_conf, qc_flags, created_at)
            SELECT gen_random_uuid(), :derived, source_fid, feature_class,
                   ST_Translate(geom, CAST(:dx AS double precision),
                                    CAST(:dy AS double precision)),
                   raw_props, extractor_conf, qc_flags, now()
            FROM source_feature
            WHERE source_id = :origin
            """
        ),
        {"derived": derived.source_id, "origin": row_b.source_id, "dx": dx, "dy": dy},
    )
    loaded = int(
        session.execute(
            text("SELECT count(*) FROM source_feature WHERE source_id = :sid"),
            {"sid": derived.source_id},
        ).scalar_one()
    )
    derived.feature_count = loaded

    session.add(
        TransformLog(
            source_id=derived.source_id,
            pipeline="offset_correction",
            n_control=pairs_used,
            rmse_m=rmse_m,
            max_resid_m=max_resid_m,
            params={
                "dx_m": dx,
                "dy_m": dy,
                "bearing_deg": _bearing_deg(dx, dy),
                "pairs_total": pairs_total,
                "pairs_used": pairs_used,
                "pairs_rejected": rejected,
                "threshold_m": threshold,
                "derived_from": str(row_b.source_id),
                "method": "median_mad",
            },
        )
    )
    session.commit()
    return derived.source_id


def estimate_offset(
    session: Session,
    source_a: UUID,
    source_b: UUID,
    *,
    policy: PolicyBundle,
    apply: bool = False,
) -> dict[str, Any]:
    """Estimate the translation that aligns source B onto source A."""
    if source_a == source_b:
        raise IngestError("same_source", "offset estimation needs two different sources")

    row_a = _require_loaded(session, source_a, "first")
    row_b = _require_loaded(session, source_b, "second")
    limits = matching_limits(policy)
    radius = _blocking_radius(row_a, row_b, limits)

    vectors, examined = _confident_vectors(
        session, source_a, source_b, radius=radius, max_pairs=limits["max_pairs"]
    )
    if not vectors:
        raise IngestError(
            "offset_no_pairs",
            f"no confident pairs between the sources within {radius:.1f} m; "
            "estimate needs at least one overlapping or nearby polygon pair",
            422,
        )

    offset_dx, offset_dy, inliers, threshold, rejected = _robust_median(vectors)
    pairs_used = len(inliers)
    residuals = [math.hypot(v[0] - offset_dx, v[1] - offset_dy) for v in inliers]
    rmse_m = math.sqrt(sum(r * r for r in residuals) / len(residuals))
    max_resid_m = max(residuals)

    # The correction is what we move B BY: undo the estimated offset.
    corr_dx, corr_dy = -offset_dx, -offset_dy
    result: dict[str, Any] = {
        "source_a": str(source_a),
        "source_b": str(source_b),
        "source_a_name": row_a.name,
        "source_b_name": row_b.name,
        "offset_dx_m": offset_dx,
        "offset_dy_m": offset_dy,
        "offset_distance_m": math.hypot(offset_dx, offset_dy),
        "correction_dx_m": corr_dx,
        "correction_dy_m": corr_dy,
        "correction_distance_m": math.hypot(corr_dx, corr_dy),
        "correction_bearing_deg": _bearing_deg(corr_dx, corr_dy),
        "pairs_examined": examined,
        "pairs_confident": len(vectors),
        "pairs_used": pairs_used,
        "pairs_rejected": rejected,
        "mad_threshold_m": threshold,
        "rmse_m": rmse_m,
        "max_residual_m": max_resid_m,
        "blocking_radius_m": radius,
        "method": "median_mad",
        "applied": None,
        "rematched": None,
    }

    if apply:
        derived_id = _apply_correction(
            session,
            row_b,
            dx=corr_dx,
            dy=corr_dy,
            pairs_used=pairs_used,
            pairs_total=len(vectors),
            rmse_m=rmse_m,
            max_resid_m=max_resid_m,
            threshold=threshold,
            rejected=rejected,
        )
        derived = session.get(SourceRegistry, derived_id)
        result["applied"] = {
            "source_id": str(derived_id),
            "name": derived.name if derived else None,
            "feature_count": derived.feature_count if derived else None,
        }
        try:
            result["rematched"] = detect_matches(session, source_a, derived_id, policy=policy)
        except IngestError as exc:
            result["rematched"] = {"error": exc.as_detail()}
    return result
