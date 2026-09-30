"""The CRS engine: rubber-sheet a source with control points, then load its features.

Two jobs, both from `backend.md` §5.2:

1. `fit_georef` fits the model ladder to the operator's control pairs, stores the winning
   model and its residuals in `transform_log`, and returns the report (leave-one-out RMSE
   per candidate, per-point residuals, blunder flags).
2. `load_features` reads the registered bytes back, reprojects them into the storage CRS
   with the PROJ pipeline pyproj gives us, applies a fitted georeferencing correction when
   one exists, and upserts one `source_feature` row per source feature.

Nothing here invents coordinates: a source with no readable geometry is skipped with a
stated reason, and every load leaves a `transform_log` row naming the operation used.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import pyogrio
import shapely
from geoalchemy2.elements import WKTElement
from shapely.ops import transform as shapely_transform
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.policy import PolicyBundle, get_policy
from app.crs.errors import CrsError
from app.crs.rubber_sheet import MODEL_ORDER, ControlPoint, select_model, transform_xy
from app.crs.transform import build_transformation
from app.db.models import SourceFeature, SourceRegistry, TransformLog
from app.ingest.archive import unpack_archive
from app.ingest.detect import is_archive, read_header
from app.ingest.store import ObjectStore
from app.qc import qc_flags_for, qc_limits

_MAX_FEATURES_PER_LOAD = 50_000
"""Upper bound on one load; larger sources must be clipped to the AOI first."""


def _matching_layer(path: Path, layer: str | None) -> str | None:
    """Pass the recorded layer name only when this file still has it.

    GDAL names a GeoJSON layer after the file it sits in, so a payload written under a
    temporary name would otherwise fail to open; anything unreadable is better left to
    the reader's default than guessed at.
    """
    if layer is None:
        return None
    try:
        available = [str(name) for name, _ in pyogrio.list_layers(str(path))]
    except Exception:
        return layer
    return layer if layer in available else None


@dataclass(frozen=True)
class GeorefLimits:
    """The georeferencing block of the policy file, with documented defaults."""

    min_control_points: int
    blunder_sigma: float
    blunder_floor_m: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "min_control_points": self.min_control_points,
            "blunder_sigma": self.blunder_sigma,
            "blunder_floor_m": self.blunder_floor_m,
        }


def georef_policy(policy: PolicyBundle) -> GeorefLimits:
    block = policy.data.get("georef") or {}
    return GeorefLimits(
        min_control_points=int(block.get("min_control_points", 4)),
        blunder_sigma=float(block.get("blunder_sigma", 3.5)),
        blunder_floor_m=float(block.get("blunder_floor_m", 0.5)),
    )


def _require_source(session: Session, source_id: UUID) -> SourceRegistry:
    row = session.get(SourceRegistry, source_id)
    if row is None:
        raise CrsError(
            "source_not_found",
            f"no source {source_id}",
            status=404,
        )
    return row


def fit_georef(
    session: Session,
    source_id: UUID,
    pairs: list[dict[str, Any]],
    *,
    policy: PolicyBundle,
    unit: str = "m",
) -> dict[str, Any]:
    """Fit the ladder to the given control pairs and persist the report."""
    row = _require_source(session, source_id)
    if not row.has_geometry:
        raise CrsError(
            "no_geometry",
            "this source has no geometry, so control points cannot be fitted to it",
        )

    limits = georef_policy(policy)
    points: list[ControlPoint] = []
    for index, pair in enumerate(pairs):
        source_xy = pair.get("from")
        target_xy = pair.get("to")
        if (
            not isinstance(source_xy, list)
            or not isinstance(target_xy, list)
            or len(source_xy) != 2
            or len(target_xy) != 2
        ):
            raise CrsError(
                "malformed_control_point",
                f"control point {index} needs 'from' and 'to' as [x, y] pairs",
            )
        points.append(
            ControlPoint(
                index=index,
                source=(float(source_xy[0]), float(source_xy[1])),
                target=(float(target_xy[0]), float(target_xy[1])),
                label=str(pair.get("label")) if pair.get("label") is not None else None,
            )
        )

    report = select_model(
        points,
        min_control_points=limits.min_control_points,
        blunder_sigma=limits.blunder_sigma,
        blunder_floor=limits.blunder_floor_m,
        unit=unit,
    ).as_dict()
    report["policy"] = limits.as_dict()

    entry = TransformLog(
        source_id=row.source_id,
        pipeline=report["model"],
        n_control=report["n_control"],
        rmse_m=report["rmse"],
        max_resid_m=report["max_residual"],
        params=report,
    )
    session.add(entry)
    session.commit()
    report["transform_log_id"] = str(entry.id)
    report["source_id"] = str(row.source_id)
    return report


def latest_georef(session: Session, source_id: UUID) -> dict[str, Any] | None:
    """The most recent control-point fit for a source, or None when there is none."""
    _require_source(session, source_id)
    entry = session.execute(
        select(TransformLog)
        .where(TransformLog.source_id == source_id, TransformLog.pipeline.in_(MODEL_ORDER))
        .order_by(TransformLog.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if entry is None:
        return None
    payload: dict[str, Any] = dict(entry.params or {})
    payload.update(
        {
            "transform_log_id": str(entry.id),
            "pipeline": entry.pipeline,
            "n_control": entry.n_control,
            "rmse": entry.rmse_m,
            "max_residual": entry.max_resid_m,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
    )
    return payload


def load_features(
    session: Session,
    store: ObjectStore,
    source_id: UUID,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Reproject a registered source into the storage CRS and upsert its observations."""
    cfg = settings or get_settings()
    row = _require_source(session, source_id)

    if row.raster is not None:
        return {
            "source_id": str(row.source_id),
            "loaded": 0,
            "skipped": "raster",
            "reason": "rasters are not vector features",
        }
    if not row.has_geometry:
        return {
            "source_id": str(row.source_id),
            "loaded": 0,
            "skipped": "no_geometry",
            "reason": "this source has no geometry",
        }
    if row.crs_used is None:
        return {
            "source_id": str(row.source_id),
            "loaded": 0,
            "skipped": "no_crs",
            "reason": "the source has no CRS to convert from",
        }

    georef = latest_georef(session, row.source_id)
    transformation = build_transformation(row.crs_used, f"EPSG:{cfg.storage_srid}")

    # Read the registered bytes back the way ingest read them: same file name, archives
    # unpacked first, so GDAL sees the layer names that were inspected at registration.
    data = store.get(row.object_key)
    with tempfile.TemporaryDirectory(prefix="samanvay-load-") as tmp:
        workdir = Path(tmp)
        stored = workdir / (Path(row.object_key).name or f"payload.{row.format}")
        stored.write_bytes(data)
        path = stored
        if is_archive(stored.name, read_header(stored)):
            unpacked = unpack_archive(
                stored,
                workdir / "unpacked",
                max_entries=cfg.max_archive_entries,
                max_bytes=cfg.max_archive_bytes,
            )
            path = unpacked.payload
        frame = pyogrio.read_dataframe(
            str(path), layer=_matching_layer(path, row.layer), fid_as_index=True
        )

    # The registry row decides what the stored coordinates mean: allow the recorded CRS
    # to override whatever pyogrio read, exactly as a declared CRS overrides at ingest.
    # Reprojection then happens once, through the pipeline that is written to the log.
    frame = frame.set_crs(row.crs_used, allow_override=True)

    records = json.loads(
        frame.drop(columns="geometry").to_json(orient="records", date_format="iso")
    )
    if len(records) != len(frame):
        # A layer without a single attribute column serialises to zero records;
        # the features still exist, they simply carry no properties.
        records = [{} for _ in range(len(frame))]
    fids = [str(fid) for fid in frame.index]

    def _correct(xy_x: Any, xy_y: Any) -> tuple[Any, Any]:
        if georef is None:
            return xy_x, xy_y
        xs = np.asarray(xy_x, dtype=np.float64)
        ys = np.asarray(xy_y, dtype=np.float64)
        stacked = np.column_stack([xs, ys])
        model = str(georef["pipeline"])
        model_params = georef["params"]["model_params"]
        corrected = transform_xy(model, model_params, stacked)
        return corrected[:, 0], corrected[:, 1]

    values: list[dict[str, Any]] = []
    classes: dict[str, int] = {}
    skipped_empty = 0
    qc = qc_limits(get_policy(cfg.policy_path))
    flag_counts: dict[str, int] = {}
    flagged_features = 0
    for fid, props, geometry in zip(fids, records, frame.geometry, strict=True):
        if geometry is None or geometry.is_empty:
            skipped_empty += 1
            continue
        # Reproject first, then correct: control pairs are given in storage-CRS metres.
        corrected = transformation.apply(geometry)
        if georef is not None:
            corrected = shapely_transform(_correct, corrected)
        if corrected.is_empty:
            skipped_empty += 1
            continue
        feature_class = feature_class_for(row.kind, corrected.geom_type)
        classes[feature_class] = classes.get(feature_class, 0) + 1
        flags = qc_flags_for(corrected, limits=qc)
        if flags:
            flagged_features += 1
            for flag in flags:
                flag_counts[flag] = flag_counts.get(flag, 0) + 1
        values.append(
            {
                "source_id": row.source_id,
                "source_fid": fid,
                "feature_class": feature_class,
                "geom": WKTElement(
                    shapely.to_wkt(corrected, rounding_precision=-1), srid=cfg.storage_srid
                ),
                "raw_props": props,
                "extractor_conf": None,
                "qc_flags": flags,
            }
        )

    if len(values) > _MAX_FEATURES_PER_LOAD:
        raise CrsError(
            "too_many_features",
            f"{len(values)} features exceed the {_MAX_FEATURES_PER_LOAD} row load limit; "
            "clip the source to the AOI first",
        )

    if values:
        statement = pg_insert(SourceFeature).values(values)
        # self-reference would be a no-op (`SET geom = features.geom`); excluded.* is
        # the incoming row, so a reload with a new georeference actually replaces it.
        statement = statement.on_conflict_do_update(
            index_elements=["source_id", "source_fid"],
            set_={
                "feature_class": statement.excluded.feature_class,
                "geom": statement.excluded.geom,
                "raw_props": statement.excluded.raw_props,
                "qc_flags": statement.excluded.qc_flags,
                "created_at": func.now(),
            },
        )
        session.execute(statement)

    payload: dict[str, Any] = {
        "source_id": str(row.source_id),
        "loaded": len(values),
        "skipped_empty": skipped_empty,
        "by_class": classes,
        "qc": {"flagged_features": flagged_features, "by_flag": flag_counts},
        "storage_srid": cfg.storage_srid,
        "pipeline": transformation.pipeline,
        "georef_applied": georef is not None,
        "georef_transform_log_id": georef["transform_log_id"] if georef else None,
    }
    entry = TransformLog(
        source_id=row.source_id,
        pipeline=f"crs:{row.crs_used}->EPSG:{cfg.storage_srid}",
        n_control=georef["n_control"] if georef else None,
        rmse_m=georef["rmse"] if georef else None,
        max_resid_m=georef["max_residual"] if georef else None,
        params={
            "crs": {"from": row.crs_used, "to": f"EPSG:{cfg.storage_srid}"},
            "projs": transformation.pipeline,
            "georef": georef["transform_log_id"] if georef else None,
            "features": len(values),
        },
    )
    session.add(entry)
    session.commit()
    payload["transform_log_id"] = str(entry.id)
    return payload


def feature_class_for(kind: str, geometry_type: str) -> str:
    """Map a source kind and a geometry type to a feature class.

    Documented heuristic, not a claim about the data: a polygon from a cadastral or
    municipal source is a parcel, lines are roads (utility for utility sources), and
    points are GNSS fixes only for GNSS sources.
    """
    shape = geometry_type.lower()
    if "polygon" in shape:
        return "building" if kind.startswith("footprint") else "parcel"
    if "line" in shape:
        return "utility_line" if kind == "utility" else "road"
    if "point" in shape:
        return "gnss_point" if kind.startswith("gnss") else "point"
    return "other"


def feature_counts(session: Session, source_id: UUID) -> dict[str, int]:
    rows = session.execute(
        select(SourceFeature.feature_class, func.count())
        .where(SourceFeature.source_id == source_id)
        .group_by(SourceFeature.feature_class)
    ).all()
    return {str(feature_class): int(count) for feature_class, count in rows}


def source_health(
    session: Session, source_id: UUID, *, settings: Settings | None = None
) -> dict[str, Any]:
    """`GET /sources/{id}/health`: coverage, CRS, transform summary and loaded counts."""
    cfg = settings or get_settings()
    row = _require_source(session, source_id)
    latest = session.execute(
        select(TransformLog)
        .where(TransformLog.source_id == row.source_id)
        .order_by(TransformLog.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    counts = feature_counts(session, row.source_id)
    flagged = 0
    by_flag: dict[str, int] = {}
    for (flags,) in session.execute(
        select(SourceFeature.qc_flags).where(SourceFeature.source_id == row.source_id)
    ).all():
        if flags:
            flagged += 1
            for flag in flags:
                by_flag[flag] = by_flag.get(flag, 0) + 1
    return {
        "source_id": str(row.source_id),
        "name": row.name,
        "kind": row.kind,
        "storage_srid": cfg.storage_srid,
        "declared_crs": row.crs_used,
        "crs_source": row.crs_source,
        "coverage": row.coverage,
        "has_geometry": row.has_geometry,
        "schema": {
            "attributes": row.attributes,
            "geometry_types": row.geometry_types,
            "layer": row.layer,
        },
        "loaded": {"features": sum(counts.values()), "by_class": counts},
        "qc": {"flagged_features": flagged, "by_flag": by_flag},
        "transform": None
        if latest is None
        else {
            "transform_log_id": str(latest.id),
            "pipeline": latest.pipeline,
            "n_control": latest.n_control,
            "rmse_m": latest.rmse_m,
            "max_resid_m": latest.max_resid_m,
            "created_at": latest.created_at.isoformat() if latest.created_at else None,
        },
        "georef": latest_georef(session, row.source_id),
    }
