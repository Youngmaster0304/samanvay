"""Feature matching: IoU-based 1-to-1 assignment between two loaded sources.

Two sources are compared in the storage CRS. Candidates come from the PostGIS
`ST_Intersects` index — that is this slice's blocking step; each polygon/polygon
candidate receives an intersection-over-union score; assignment is greedy
(highest IoU first, every feature used at most once). Accept and cap thresholds
come from the `matching:` policy block.

Honest limits of this slice, stated so nobody over-reads the numbers:

- polygon vs polygon only — lines and points need the full scorer,
- greedy assignment, not Hungarian (scipy is not in the image yet),
- no attribute, direction, or split/merge evidence in the score,
- disjoint features are not candidates (an AOI rule is a later stage).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from shapely.geometry import shape as shapely_shape
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.policy import PolicyBundle
from app.db.models import FeatureMatch, SourceRegistry
from app.ingest.errors import IngestError

_PAIR_COUNT = text(
    """
    SELECT count(*)
    FROM source_feature a
    JOIN source_feature b ON ST_Intersects(a.geom, b.geom)
    WHERE a.source_id = :sa AND b.source_id = :sb
    """
)

_CANDIDATES = text(
    """
    SELECT a.source_fid AS fid_a,
           b.source_fid AS fid_b,
           ST_AsGeoJSON(a.geom) AS geom_a,
           ST_AsGeoJSON(b.geom) AS geom_b
    FROM source_feature a
    JOIN source_feature b ON ST_Intersects(a.geom, b.geom)
    WHERE a.source_id = :sa AND b.source_id = :sb
    """
)

_POLYGON_TYPES = frozenset({"Polygon", "MultiPolygon"})


def matching_limits(policy: PolicyBundle) -> dict[str, float]:
    block = policy.data.get("matching", {})
    if not isinstance(block, dict):
        raise IngestError("bad_policy", "the policy 'matching:' block must be a mapping")
    limits: dict[str, float] = {}
    for key in ("accept_threshold", "max_pairs"):
        value = block.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise IngestError(
                "bad_policy", f"policy 'matching.{key}' must be a number in {policy.path}"
            )
        limits[key] = float(value)
    return limits


def _require_loaded(session: Session, source_id: UUID, label: str) -> SourceRegistry:
    row = session.get(SourceRegistry, source_id)
    if row is None:
        raise IngestError("source_not_found", f"{label} source {source_id} is not registered", 404)
    loaded: Any = session.execute(
        text("SELECT count(*) FROM source_feature WHERE source_id = :sid"), {"sid": source_id}
    ).scalar_one()
    if int(loaded) == 0:
        raise IngestError(
            "source_not_loaded",
            f"{label} source {source_id} has no loaded features; "
            f"run POST /sources/{source_id}/load first",
        )
    return row


def detect_matches(
    session: Session,
    source_a: UUID,
    source_b: UUID,
    *,
    policy: PolicyBundle,
) -> dict[str, Any]:
    """Match polygon features of two loaded sources by IoU and persist the pairs."""
    if source_a == source_b:
        raise IngestError("same_source", "matching needs two different sources")

    row_a = _require_loaded(session, source_a, "first")
    row_b = _require_loaded(session, source_b, "second")
    limits = matching_limits(policy)

    params = {"sa": source_a, "sb": source_b}
    count = int(session.execute(_PAIR_COUNT, params).scalar_one())
    if count > limits["max_pairs"]:
        raise IngestError(
            "too_many_pairs",
            f"{count} intersecting pairs exceed matching.max_pairs="
            f"{int(limits['max_pairs'])} in {policy.path}; clip the sources to a smaller AOI",
        )

    rows = session.execute(_CANDIDATES, params).mappings().all()
    candidates: list[tuple[float, str, str]] = []
    skipped = 0
    for row in rows:
        geom_a = shapely_shape(json.loads(row["geom_a"]))
        geom_b = shapely_shape(json.loads(row["geom_b"]))
        if geom_a.geom_type not in _POLYGON_TYPES or geom_b.geom_type not in _POLYGON_TYPES:
            skipped += 1
            continue
        union_area = geom_a.union(geom_b).area
        if union_area <= 0:
            continue
        iou = geom_a.intersection(geom_b).area / union_area
        if iou >= limits["accept_threshold"]:
            candidates.append((float(iou), str(row["fid_a"]), str(row["fid_b"])))

    # Greedy one-to-one: best IoU first, each feature assigned at most once.
    candidates.sort(reverse=True)
    used_a: set[str] = set()
    used_b: set[str] = set()
    assigned: list[tuple[float, str, str]] = []
    for iou, fid_a, fid_b in candidates:
        if fid_a in used_a or fid_b in used_b:
            continue
        used_a.add(fid_a)
        used_b.add(fid_b)
        assigned.append((iou, fid_a, fid_b))

    # Matches carry no decision history yet: a re-run replaces the pair whole.
    session.execute(
        text("DELETE FROM feature_match WHERE source_a = :sa AND source_b = :sb"), params
    )
    for iou, fid_a, fid_b in assigned:
        session.add(
            FeatureMatch(
                source_a=source_a,
                source_b=source_b,
                fid_a=fid_a,
                fid_b=fid_b,
                score=iou,
                method="iou_greedy",
            )
        )
    session.commit()

    scores = [iou for iou, _, _ in assigned]
    return {
        "source_a": str(source_a),
        "source_b": str(source_b),
        "source_a_name": row_a.name,
        "source_b_name": row_b.name,
        "pairs_examined": count,
        "polygon_candidates": len(candidates),
        "assigned": len(assigned),
        "non_polygon_pairs_skipped": skipped,
        "score_min": min(scores) if scores else None,
        "score_mean": sum(scores) / len(scores) if scores else None,
        "score_max": max(scores) if scores else None,
        "policy": {
            "name": policy.name,
            "version": policy.version,
            "path": policy.path,
            "limits": limits,
        },
    }


def list_matches(
    session: Session,
    *,
    source: UUID | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Accepted matches newest first, with both source names for the workbench."""
    stmt = select(FeatureMatch)
    if source is not None:
        stmt = stmt.where((FeatureMatch.source_a == source) | (FeatureMatch.source_b == source))
    stmt = stmt.order_by(FeatureMatch.created_at.desc()).limit(limit)
    rows = session.execute(stmt).scalars().all()

    name_cache: dict[UUID, str] = {}

    def _name(source_id: UUID) -> str:
        if source_id not in name_cache:
            registry = session.get(SourceRegistry, source_id)
            name_cache[source_id] = registry.name if registry else str(source_id)
        return name_cache[source_id]

    items = [
        {
            "match_id": str(match.match_id),
            "source_a": str(match.source_a),
            "source_b": str(match.source_b),
            "source_a_name": _name(match.source_a),
            "source_b_name": _name(match.source_b),
            "fid_a": match.fid_a,
            "fid_b": match.fid_b,
            "score": match.score,
            "method": match.method,
            "created_at": match.created_at.isoformat(),
        }
        for match in rows
    ]
    return {"items": items, "total": len(items)}
