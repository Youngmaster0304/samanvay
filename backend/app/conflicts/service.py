"""Conflict detection: geometry overlap and boundary crossings between two sources.

Two registered, loaded sources are compared in the storage CRS. Each intersecting
feature pair is classified from the geometry of the intersection itself:

- polygon against polygon with area -> `overlap`, severity from the area,
- a line with part of itself outside the other feature -> `boundary_crossing`,
  severity from the length outside,
- anything else (roads meeting at a junction, lines that only touch, polygons that
  merely share an edge) is not a disagreement between sources and is not queued.

All severity thresholds come from the `conflicts:` policy block. Re-running detection
replaces only rows still in `queue`; decided rows are append-only history.

Honest limits of this slice: there is no source hierarchy yet, so nothing is
auto-resolved — every detected pair waits for a reviewer; disjoint pairs are not
compared at all (they need an AOI rule, a later stage).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from geoalchemy2.elements import WKTElement
from shapely import to_wkt
from shapely.geometry import shape as shapely_shape
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.policy import PolicyBundle
from app.db.models import Conflict, ConflictDecision, SourceRegistry
from app.ingest.errors import IngestError

_PAIR_COUNT = text(
    """
    SELECT count(*)
    FROM source_feature a
    JOIN source_feature b ON ST_Intersects(a.geom, b.geom)
    WHERE a.source_id = :sa AND b.source_id = :sb
    """
)

_PAIRS = text(
    """
    SELECT a.source_fid AS fid_a,
           b.source_fid AS fid_b,
           ST_AsGeoJSON(ST_Intersection(a.geom, b.geom)) AS geom_json,
           ST_GeometryType(a.geom) AS type_a,
           ST_GeometryType(b.geom) AS type_b,
           CASE
             WHEN ST_GeometryType(ST_Intersection(a.geom, b.geom))
                  IN ('ST_Polygon', 'ST_MultiPolygon')
             THEN ST_Area(ST_Intersection(a.geom, b.geom))
           END AS area_m2,
           CASE
             WHEN ST_GeometryType(a.geom) IN ('ST_LineString', 'ST_MultiLineString')
              AND ST_GeometryType(b.geom) IN ('ST_Polygon', 'ST_MultiPolygon')
             THEN ST_Length(ST_Difference(a.geom, b.geom))
             WHEN ST_GeometryType(b.geom) IN ('ST_LineString', 'ST_MultiLineString')
              AND ST_GeometryType(a.geom) IN ('ST_Polygon', 'ST_MultiPolygon')
             THEN ST_Length(ST_Difference(b.geom, a.geom))
           END AS outside_m
    FROM source_feature a
    JOIN source_feature b ON ST_Intersects(a.geom, b.geom)
    WHERE a.source_id = :sa AND b.source_id = :sb
    """
)


def conflict_limits(policy: PolicyBundle) -> dict[str, float]:
    block = policy.data.get("conflicts", {})
    if not isinstance(block, dict):
        raise IngestError("bad_policy", "the policy 'conflicts:' block must be a mapping")
    required = (
        "overlap_high_m2",
        "overlap_medium_m2",
        "crossing_high_m",
        "crossing_medium_m",
        "max_pairs",
    )
    limits: dict[str, float] = {}
    for key in required:
        value = block.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise IngestError(
                "bad_policy", f"policy 'conflicts.{key}' must be a number in {policy.path}"
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


def _severity(area_m2: float | None, outside_m: float | None, limits: dict[str, float]) -> str:
    if area_m2 is not None:
        if area_m2 >= limits["overlap_high_m2"]:
            return "high"
        return "medium" if area_m2 >= limits["overlap_medium_m2"] else "low"
    outside = outside_m or 0.0
    if outside >= limits["crossing_high_m"]:
        return "high"
    return "medium" if outside >= limits["crossing_medium_m"] else "low"


def detect_conflicts(
    session: Session,
    source_a: UUID,
    source_b: UUID,
    *,
    policy: PolicyBundle,
) -> dict[str, Any]:
    """Compare two loaded sources and persist what they disagree about."""
    if source_a == source_b:
        raise IngestError("same_source", "conflict detection needs two different sources")

    row_a = _require_loaded(session, source_a, "first")
    row_b = _require_loaded(session, source_b, "second")
    limits = conflict_limits(policy)

    params = {"sa": source_a, "sb": source_b}
    count = int(session.execute(_PAIR_COUNT, params).scalar_one())
    if count > limits["max_pairs"]:
        raise IngestError(
            "too_many_pairs",
            f"{count} intersecting pairs exceed conflicts.max_pairs="
            f"{int(limits['max_pairs'])} in {policy.path}; clip the sources to a smaller AOI",
        )

    rows = session.execute(_PAIRS, params).mappings().all()
    srid = get_settings().storage_srid

    # Only queue rows are replaced; decided ones stay as history, and the unique
    # (source_a, source_b, fid_a, fid_b) key keeps re-runs idempotent per pair.
    session.execute(
        text("DELETE FROM conflict WHERE source_a = :sa AND source_b = :sb AND state = 'queue'"),
        params,
    )

    pending: list[Conflict] = []
    by_severity: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for row in rows:
        area = float(row["area_m2"]) if row["area_m2"] is not None else None
        outside = float(row["outside_m"]) if row["outside_m"] is not None else None
        if area is not None:
            kind = "overlap"
            reason = (
                f"{area:.1f} m² of feature {row['fid_a']} in '{row_a.name}' overlaps "
                f"feature {row['fid_b']} in '{row_b.name}'; "
                f"policy {policy.name} v{policy.version} overlap thresholds "
                f"medium>={limits['overlap_medium_m2']:g} m² high>={limits['overlap_high_m2']:g} m²"
            )
        elif outside is not None and outside > 0:
            kind = "boundary_crossing"
            reason = (
                f"{outside:.1f} m of feature {row['fid_a']} in '{row_a.name}' falls outside "
                f"feature {row['fid_b']} in '{row_b.name}'; "
                f"policy {policy.name} v{policy.version} crossing thresholds "
                f"medium>={limits['crossing_medium_m']:g} m high>={limits['crossing_high_m']:g} m"
            )
        else:
            # lines meeting at a point, edges that merely touch: not a disagreement.
            continue

        severity = _severity(area, outside, limits)
        geom = shapely_shape(json.loads(row["geom_json"]))
        pending.append(
            Conflict(
                source_a=source_a,
                source_b=source_b,
                fid_a=str(row["fid_a"]),
                fid_b=str(row["fid_b"]),
                type=kind,
                severity=severity,
                state="queue",
                area_m2=area,
                outside_m=outside,
                reason=reason,
                geom=WKTElement(to_wkt(geom, rounding_precision=-1), srid=srid),
            )
        )

    # A row already decided keeps its history: skip it instead of clobbering it.
    inserted: list[Conflict] = []
    for conflict in pending:
        existing = session.execute(
            text(
                "SELECT 1 FROM conflict WHERE source_a = :sa AND source_b = :sb "
                "AND fid_a = :fa AND fid_b = :fb"
            ),
            {
                "sa": conflict.source_a,
                "sb": conflict.source_b,
                "fa": conflict.fid_a,
                "fb": conflict.fid_b,
            },
        ).first()
        if existing is None:
            session.add(conflict)
            inserted.append(conflict)
            by_severity[conflict.severity] = by_severity.get(conflict.severity, 0) + 1
            by_type[conflict.type] = by_type.get(conflict.type, 0) + 1
    session.commit()

    return {
        "source_a": str(source_a),
        "source_b": str(source_b),
        "source_a_name": row_a.name,
        "source_b_name": row_b.name,
        "pairs_examined": count,
        "created": len(inserted),
        "by_severity": by_severity,
        "by_type": by_type,
        "policy": {
            "name": policy.name,
            "version": policy.version,
            "path": policy.path,
            "limits": limits,
        },
    }


def list_conflicts(
    session: Session,
    *,
    state: str | None = None,
    conflict_type: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """The reviewer queue: conflicts newest first, with source names and evidence geometry."""
    stmt = select(Conflict, func.ST_AsGeoJSON(Conflict.geom).label("geom_json"))
    if state:
        stmt = stmt.where(Conflict.state == state)
    if conflict_type:
        stmt = stmt.where(Conflict.type == conflict_type)
    stmt = stmt.order_by(Conflict.created_at.desc()).limit(limit)

    rows = session.execute(stmt).all()
    name_cache: dict[UUID, str] = {}

    def _name(source_id: UUID) -> str:
        if source_id not in name_cache:
            registry = session.get(SourceRegistry, source_id)
            name_cache[source_id] = registry.name if registry else str(source_id)
        return name_cache[source_id]

    items: list[dict[str, Any]] = []
    for conflict, geom_json in rows:
        items.append(
            {
                "conflict_id": str(conflict.conflict_id),
                "source_a": str(conflict.source_a),
                "source_b": str(conflict.source_b),
                "source_a_name": _name(conflict.source_a),
                "source_b_name": _name(conflict.source_b),
                "fid_a": conflict.fid_a,
                "fid_b": conflict.fid_b,
                "type": conflict.type,
                "severity": conflict.severity,
                "state": conflict.state,
                "area_m2": conflict.area_m2,
                "outside_m": conflict.outside_m,
                "reason": conflict.reason,
                "geometry": json.loads(geom_json) if geom_json else None,
                "created_at": conflict.created_at.isoformat(),
            }
        )
    return {"items": items, "total": len(items)}


DECISION_STATE = {
    "accept_a": "resolved",
    "accept_b": "resolved",
    "defer": "deferred",
    "reject": "dismissed",
}


def decide_conflict(
    session: Session,
    conflict_id: UUID,
    *,
    action: str,
    reason_code: str,
    actor: str,
) -> dict[str, Any]:
    """Record one reviewer decision. Append-only: the decision row is never rewritten."""
    if action not in DECISION_STATE:
        raise IngestError(
            "bad_action",
            f"unknown action '{action}'; expected one of {sorted(DECISION_STATE)}",
        )
    conflict = session.get(Conflict, conflict_id)
    if conflict is None:
        raise IngestError("conflict_not_found", f"conflict {conflict_id} does not exist", 404)
    if conflict.state != "queue":
        raise IngestError(
            "already_decided",
            f"conflict {conflict_id} is '{conflict.state}', not in the queue",
            409,
        )

    conflict.state = DECISION_STATE[action]
    decision = ConflictDecision(
        conflict_id=conflict_id, actor=actor, action=action, reason_code=reason_code
    )
    session.add(decision)
    session.commit()

    return {
        "conflict_id": str(conflict_id),
        "state": conflict.state,
        "decision": {
            "decision_id": str(decision.decision_id),
            "actor": actor,
            "action": action,
            "reason_code": reason_code,
            "created_at": decision.created_at.isoformat(),
        },
    }
