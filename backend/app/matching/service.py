"""Feature matching: scored 1-to-1 assignment between two loaded sources (Stage 4).

Blocking is a PostGIS `ST_DWithin` query: the radius is the policy's
`matching.search_radius_m` widened by 3x the two sources' combined declared
sigma, so a layer that is offset from the other (and therefore does not
intersect it at all) still produces candidates. Each polygon/polygon candidate
receives seven pair features — IoU, intersection over min-area, centroid
distance, area ratio, orientation difference, compactness difference and
attribute similarity — a logistic scorer turns them into one score in [0, 1],
and the Hungarian algorithm (scipy, solved per connected component of the
candidate graph) assigns pairs one-to-one before the accept threshold is
applied. Every accepted pair is stored with the feature values the scorer saw.

Honest limits of this slice, stated so nobody over-reads the numbers:

- polygon vs polygon only — lines and points need the full scorer,
- the scorer is a weighted prior from the policy, not a learned model
  (v1 LightGBM needs 200-300 hand-labeled pairs from our AOI),
- attribute evidence is exact/fuzzy string similarity over shared raw_props,
- split/merge grouping is not implemented yet,
- components whose dense cost matrix would be absurd fall back to greedy
  assignment, and the count of those fallbacks is reported.
"""

from __future__ import annotations

import json
import math
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from scipy.optimize import linear_sum_assignment
from shapely.geometry import shape as shapely_shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.policy import PolicyBundle
from app.db.models import FeatureMatch, SourceRegistry
from app.ingest.errors import IngestError

_FEATURE_KEYS = (
    "iou",
    "iom",
    "distance",
    "area_ratio",
    "orientation",
    "compactness",
    "attribute",
)
_POLYGON_TYPES = frozenset({"Polygon", "MultiPolygon"})

# A component whose dense matrix would hold more cells than this goes greedy.
_MAX_DENSE_CELLS = 1_000_000

_NEAR_COUNT = text(
    """
    SELECT count(*)
    FROM source_feature a
    JOIN source_feature b ON ST_DWithin(a.geom, b.geom, :radius)
    WHERE a.source_id = :sa AND b.source_id = :sb
    """
)

_NEAR = text(
    """
    SELECT a.source_fid AS fid_a,
           b.source_fid AS fid_b,
           ST_AsGeoJSON(a.geom) AS geom_a,
           ST_AsGeoJSON(b.geom) AS geom_b,
           a.raw_props AS props_a,
           b.raw_props AS props_b
    FROM source_feature a
    JOIN source_feature b ON ST_DWithin(a.geom, b.geom, :radius)
    WHERE a.source_id = :sa AND b.source_id = :sb
    """
)


def matching_limits(policy: PolicyBundle) -> dict[str, float]:
    """The scalar thresholds the matcher is allowed to use, validated from policy."""
    block = policy.data.get("matching", {})
    if not isinstance(block, dict):
        raise IngestError("bad_policy", "the policy 'matching:' block must be a mapping")
    limits: dict[str, float] = {}
    for key in ("accept_threshold", "max_pairs", "search_radius_m"):
        value = block.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise IngestError(
                "bad_policy", f"policy 'matching.{key}' must be a number in {policy.path}"
            )
        limits[key] = float(value)
    return limits


def matching_weights(policy: PolicyBundle) -> tuple[dict[str, float], float]:
    """The logistic scorer's weights and bias, validated from policy."""
    block = policy.data.get("matching", {})
    if not isinstance(block, dict):
        raise IngestError("bad_policy", "the policy 'matching:' block must be a mapping")
    bias = block.get("bias")
    if not isinstance(bias, (int, float)) or isinstance(bias, bool):
        raise IngestError("bad_policy", f"policy 'matching.bias' must be a number in {policy.path}")
    raw = block.get("weights")
    if not isinstance(raw, dict):
        raise IngestError(
            "bad_policy", f"policy 'matching.weights' must be a mapping in {policy.path}"
        )
    missing = [key for key in _FEATURE_KEYS if key not in raw]
    if missing:
        raise IngestError(
            "bad_policy",
            f"policy 'matching.weights' is missing {', '.join(missing)} in {policy.path}",
        )
    weights: dict[str, float] = {}
    for key in _FEATURE_KEYS:
        value = raw[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise IngestError(
                "bad_policy",
                f"policy 'matching.weights.{key}' must be a number in {policy.path}",
            )
        weights[key] = float(value)
    return weights, float(bias)


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


def _blocking_radius(
    row_a: SourceRegistry, row_b: SourceRegistry, limits: dict[str, float]
) -> float:
    """Policy radius widened by 3x the combined declared sigma [P heuristic]."""
    sigma_a = max(row_a.sigma_m or 0.0, 0.0)
    sigma_b = max(row_b.sigma_m or 0.0, 0.0)
    combined = math.sqrt(sigma_a * sigma_a + sigma_b * sigma_b)
    return limits["search_radius_m"] + 3.0 * combined


def _largest_polygon(geometry: BaseGeometry) -> Any:
    if geometry.geom_type == "Polygon":
        return geometry
    return max(geometry.geoms, key=lambda part: part.area)


def _axis_deg(geometry: BaseGeometry) -> float:
    """Principal-axis bearing of the largest ring, in degrees mod 180 (PCA)."""
    ring = list(_largest_polygon(geometry).exterior.coords)
    if len(ring) < 3:
        return 0.0
    mean_x = sum(point[0] for point in ring) / len(ring)
    mean_y = sum(point[1] for point in ring) / len(ring)
    sxx = sum((point[0] - mean_x) ** 2 for point in ring) / len(ring)
    syy = sum((point[1] - mean_y) ** 2 for point in ring) / len(ring)
    sxy = sum((point[0] - mean_x) * (point[1] - mean_y) for point in ring) / len(ring)
    theta = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
    return math.degrees(theta) % 180.0


def _compactness(geometry: BaseGeometry) -> float:
    polygon = _largest_polygon(geometry)
    # shapely's Polygon.length is the ring perimeter (exterior + interiors).
    if polygon.length <= 0:
        return 0.0
    return float(min(1.0, 4.0 * math.pi * polygon.area / (polygon.length**2)))


def _attribute_similarity(props_a: Any, props_b: Any) -> float:
    """Best exact/fuzzy similarity over shared scalar attributes, in [0, 1]."""
    if not isinstance(props_a, dict) or not isinstance(props_b, dict):
        return 0.0
    shared = [
        key
        for key in props_a
        if key in props_b
        and (
            isinstance(props_a[key], (str, int, float))
            and isinstance(props_b[key], (str, int, float))
        )
    ][:8]
    best = 0.0
    for key in shared:
        left, right = props_a[key], props_b[key]
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            if float(left) == float(right):
                return 1.0
            continue
        text_left = str(left).strip().casefold()
        text_right = str(right).strip().casefold()
        if not text_left or not text_right:
            continue
        if text_left == text_right:
            return 1.0
        best = max(best, SequenceMatcher(None, text_left, text_right).ratio())
    return float(best)


def pair_features(
    geometry_a: BaseGeometry,
    geometry_b: BaseGeometry,
    props_a: Any,
    props_b: Any,
    *,
    radius: float,
) -> dict[str, float]:
    """The seven normalised scorer inputs plus the raw centroid distance (metres)."""
    union_area = geometry_a.union(geometry_b).area
    if union_area <= 0:
        raise IngestError("empty_union", "candidate pair has an empty union")
    intersection = geometry_a.intersection(geometry_b).area
    area_a, area_b = float(geometry_a.area), float(geometry_b.area)
    min_area = min(area_a, area_b)
    max_area = max(area_a, area_b)
    iou = intersection / union_area
    iom = intersection / min_area if min_area > 0 else 0.0
    distance_m = float(geometry_a.centroid.distance(geometry_b.centroid))
    orientation = abs(_axis_deg(geometry_a) - _axis_deg(geometry_b))
    orientation = min(orientation, 180.0 - orientation)  # fold to [0, 90]
    return {
        "iou": float(min(1.0, iou)),
        "iom": float(min(1.0, iom)),
        "distance": float(min(1.0, distance_m / radius)) if radius > 0 else 0.0,
        "distance_m": distance_m,
        "area_ratio": float(min_area / max_area) if max_area > 0 else 0.0,
        "orientation": float(orientation / 90.0),
        "compactness": float(abs(_compactness(geometry_a) - _compactness(geometry_b))),
        "attribute": _attribute_similarity(props_a, props_b),
    }


def _score(features: dict[str, float], weights: dict[str, float], bias: float) -> float:
    """Logistic squashing of the weighted feature sum, in (0, 1)."""
    z = bias + sum(weights[key] * features[key] for key in _FEATURE_KEYS)
    z = max(-60.0, min(60.0, float(z)))
    return 1.0 / (1.0 + math.exp(-z))


def _greedy_component(
    edges: list[tuple[float, str, str, dict[str, float]]], accept: float
) -> list[tuple[float, str, str, dict[str, float]]]:
    used_a: set[str] = set()
    used_b: set[str] = set()
    accepted: list[tuple[float, str, str, dict[str, float]]] = []
    for score, fid_a, fid_b, features in sorted(edges, reverse=True):
        if score < accept or fid_a in used_a or fid_b in used_b:
            continue
        used_a.add(fid_a)
        used_b.add(fid_b)
        accepted.append((score, fid_a, fid_b, features))
    return accepted


def assign_hungarian(
    candidates: list[tuple[str, str, dict[str, float], float]],
    *,
    accept: float,
) -> tuple[list[tuple[float, str, str, dict[str, float]]], int]:
    """One-to-one assignment via scipy's Hungarian solver per candidate component.

    Returns the accepted pairs `(score, fid_a, fid_b, features)` and how many
    components fell back to greedy because their dense matrix was too large.
    """
    graph: dict[str, set[str]] = {}
    for fid_a, fid_b, _, _ in candidates:
        node_a, node_b = f"a|{fid_a}", f"b|{fid_b}"
        graph.setdefault(node_a, set()).add(node_b)
        graph.setdefault(node_b, set()).add(node_a)

    accepted: list[tuple[float, str, str, dict[str, float]]] = []
    seen: set[str] = set()
    fallbacks = 0
    for start in graph:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        component: list[str] = []
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbour in graph[node]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        rows = sorted(node for node in component if node.startswith("a|"))
        cols = sorted(node for node in component if node.startswith("b|"))
        if len(rows) * len(cols) > _MAX_DENSE_CELLS:
            fallbacks += 1
            edges = [
                (score, fid_a, fid_b, features)
                for fid_a, fid_b, features, score in candidates
                if f"a|{fid_a}" in rows
            ]
            accepted.extend(_greedy_component(edges, accept))
            continue

        row_index = {node: i for i, node in enumerate(rows)}
        col_index = {node: j for j, node in enumerate(cols)}
        cost = [[1.0] * len(cols) for _ in range(len(rows))]
        scored: dict[tuple[int, int], tuple[float, str, str, dict[str, float]]] = {}
        for fid_a, fid_b, features, score in candidates:
            node_a, node_b = f"a|{fid_a}", f"b|{fid_b}"
            if node_a not in row_index or node_b not in col_index:
                continue
            i, j = row_index[node_a], col_index[node_b]
            cost[i][j] = 1.0 - score
            scored[(i, j)] = (score, fid_a, fid_b, features)

        assigned_rows, assigned_cols = linear_sum_assignment(cost)
        for i, j in zip(assigned_rows, assigned_cols, strict=True):
            found = scored.get((int(i), int(j)))
            if found is None:
                continue  # a zero-score filler cell of the rectangular assignment
            score, fid_a, fid_b, features = found
            if score >= accept:
                accepted.append((score, fid_a, fid_b, features))
    return accepted, fallbacks


def detect_matches(
    session: Session,
    source_a: UUID,
    source_b: UUID,
    *,
    policy: PolicyBundle,
) -> dict[str, Any]:
    """Match polygon features of two loaded sources and persist the accepted pairs."""
    if source_a == source_b:
        raise IngestError("same_source", "matching needs two different sources")

    row_a = _require_loaded(session, source_a, "first")
    row_b = _require_loaded(session, source_b, "second")
    limits = matching_limits(policy)
    weights, bias = matching_weights(policy)
    radius = _blocking_radius(row_a, row_b, limits)

    params = {"sa": source_a, "sb": source_b, "radius": radius}
    count = int(session.execute(_NEAR_COUNT, params).scalar_one())
    if count > limits["max_pairs"]:
        raise IngestError(
            "too_many_pairs",
            f"{count} nearby pairs exceed matching.max_pairs="
            f"{int(limits['max_pairs'])} in {policy.path}; clip the sources to a smaller AOI",
        )

    rows = session.execute(_NEAR, params).mappings().all()
    candidates: list[tuple[str, str, dict[str, float], float]] = []
    skipped = 0
    near_miss = 0
    for row in rows:
        geometry_a = shapely_shape(json.loads(row["geom_a"]))
        geometry_b = shapely_shape(json.loads(row["geom_b"]))
        if geometry_a.geom_type not in _POLYGON_TYPES or geometry_b.geom_type not in _POLYGON_TYPES:
            skipped += 1
            continue
        if geometry_a.union(geometry_b).area <= 0:
            continue
        features = pair_features(
            geometry_a, geometry_b, row["props_a"], row["props_b"], radius=radius
        )
        if features["iou"] <= 0.0:
            near_miss += 1
        candidates.append(
            (str(row["fid_a"]), str(row["fid_b"]), features, _score(features, weights, bias))
        )

    accepted, fallbacks = assign_hungarian(candidates, accept=limits["accept_threshold"])

    # Matches carry no decision history yet: a re-run replaces the pair whole.
    session.execute(
        text("DELETE FROM feature_match WHERE source_a = :sa AND source_b = :sb"), params
    )
    for score, fid_a, fid_b, features in accepted:
        session.add(
            FeatureMatch(
                source_a=source_a,
                source_b=source_b,
                fid_a=fid_a,
                fid_b=fid_b,
                score=score,
                method="hungarian",
                pair_features=features,
            )
        )
    session.commit()

    scores = [score for score, _, _, _ in accepted]
    return {
        "source_a": str(source_a),
        "source_b": str(source_b),
        "source_a_name": row_a.name,
        "source_b_name": row_b.name,
        "pairs_examined": count,
        "polygon_candidates": len(candidates),
        "near_miss_candidates": near_miss,
        "assigned": len(accepted),
        "non_polygon_pairs_skipped": skipped,
        "blocking_radius_m": radius,
        "assignment": "hungarian",
        "greedy_fallback_components": fallbacks,
        "score_min": min(scores) if scores else None,
        "score_mean": sum(scores) / len(scores) if scores else None,
        "score_max": max(scores) if scores else None,
        "policy": {
            "name": policy.name,
            "version": policy.version,
            "path": policy.path,
            "limits": limits,
            "weights": weights,
            "bias": bias,
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
            "pair_features": match.pair_features,
            "created_at": match.created_at.isoformat(),
        }
        for match in rows
    ]
    return {"items": items, "total": len(items)}
