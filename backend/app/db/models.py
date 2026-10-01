"""SQLAlchemy models.

`source_registry` arrives with Stage 1; `source_feature` and `transform_log` with Stage 3
(the CRS engine). The observation, match, conflict, decision, field-task and owner tables
arrive with the stages that write them, so the schema always describes something the code
can actually produce.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Date, DateTime, Double, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.base import Base


def utcnow() -> datetime:
    """Timezone-aware now(); the database column is timestamptz."""
    return datetime.now(UTC)


class SourceRegistry(Base):
    """One row per distinct uploaded file: what it is, where it came from, what is in it.

    The columns beyond `backend.md` §4 (`format`, `crs_used`, `crs_source`, `object_key`,
    `size_bytes`, `feature_count`, `coverage`, `attributes`, `raster`, `notes`,
    `client_key`) are what ingest actually learns while reading the file. They are part
    of the same provenance record rather than a second table, because a source without
    its inspection result cannot be described honestly.
    """

    __tablename__ = "source_registry"

    __table_args__ = (
        # Same bytes, same kind, same source: one row. Different kind, new row.
        Index(
            "uq_source_registry_sha256_kind",
            "sha256",
            "kind",
            unique=True,
        ),
        Index("ix_source_registry_client_key", "client_key", unique=True),
        Index("ix_source_registry_kind", "kind"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # What it is, and who says so
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32))
    authority: Mapped[str | None] = mapped_column(Text)
    licence: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    vintage: Mapped[date | None] = mapped_column(Date)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sigma_m: Mapped[float | None] = mapped_column(Double)

    # Identity of the bytes
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    object_key: Mapped[str] = mapped_column(Text)
    client_key: Mapped[str | None] = mapped_column(Text)

    # What the file turned out to be
    format: Mapped[str] = mapped_column(String(32))
    crs_original: Mapped[str | None] = mapped_column(Text)
    crs_declared: Mapped[str | None] = mapped_column(Text)
    crs_used: Mapped[str | None] = mapped_column(Text)
    crs_source: Mapped[str] = mapped_column(String(32))
    has_geometry: Mapped[bool] = mapped_column(Boolean, default=True)
    feature_count: Mapped[int | None] = mapped_column(Integer)
    coverage: Mapped[list[float] | None] = mapped_column(JSONB)  # [minx, miny, maxx, maxy]
    attributes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    geometry_types: Mapped[list[str]] = mapped_column(JSONB, default=list)
    layer: Mapped[str | None] = mapped_column(Text)
    layers: Mapped[list[str]] = mapped_column(JSONB, default=list)
    raster: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[list[str]] = mapped_column(JSONB, default=list)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default="now()"
    )

    def __repr__(self) -> str:
        return f"<SourceRegistry {self.source_id} {self.kind} {self.sha256[:12]}>"


class SourceFeature(Base):
    """One observation of one source feature, in the storage CRS.

    Rows are keyed by `(source_id, source_fid)`, so reloading a source after a better
    georeferencing fit updates the observation instead of duplicating it. Geometry is
    never invented here: it comes from the registered file, reprojected (and, when a
    control-point fit exists, rubber-sheeted) by `app.crs.service.load_features`.
    """

    __tablename__ = "source_feature"

    __table_args__ = (
        Index("uq_source_feature_source_fid", "source_id", "source_fid", unique=True),
        Index("ix_source_feature_class", "feature_class"),
    )

    obs_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_fid: Mapped[str] = mapped_column(Text)
    feature_class: Mapped[str] = mapped_column(Text)

    # Storage CRS from settings: the geometry type must match what the migration wrote.
    geom: Mapped[Any] = mapped_column(
        Geometry(
            "GEOMETRY",
            srid=get_settings().storage_srid,
            spatial_index=False,  # the gist index is created by migration 0003
            nullable=False,
        )
    )

    raw_props: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    extractor_conf: Mapped[float | None] = mapped_column(Double)
    qc_flags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default="now()"
    )

    def __repr__(self) -> str:
        return f"<SourceFeature {self.obs_id} src={self.source_id} {self.feature_class}>"


class TransformLog(Base):
    """One CRS or rubber-sheet step, with the parameters and residuals that justify it.

    `pipeline` is the PROJ pipeline for a plain reprojection, or the winning model name
    (`affine`, `poly2`, `tps`) for a control-point fit. Everything measured — leave-one-out
    RMSE per candidate, per-point residuals, blunder flags — lives in `params`.
    """

    __tablename__ = "transform_log"

    __table_args__ = (Index("ix_transform_log_source", "source_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    pipeline: Mapped[str] = mapped_column(Text)
    n_control: Mapped[int | None] = mapped_column(Integer)
    rmse_m: Mapped[float | None] = mapped_column(Double)
    max_resid_m: Mapped[float | None] = mapped_column(Double)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default="now()"
    )

    def __repr__(self) -> str:
        return f"<TransformLog {self.id} {self.pipeline} n={self.n_control}>"


class Conflict(Base):
    """One detected geometric disagreement between two loaded sources.

    Severity comes from the `conflicts:` policy block, never from code constants.
    `state` moves queue -> resolved | deferred | dismissed through decisions;
    `conflict_decision` keeps every action append-only (backend.md §5.6).
    """

    __tablename__ = "conflict"

    __table_args__ = (
        Index(
            "uq_conflict_pair_features",
            "source_a",
            "source_b",
            "fid_a",
            "fid_b",
            unique=True,
        ),
        Index("ix_conflict_state", "state"),
    )

    conflict_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_a: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_b: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fid_a: Mapped[str] = mapped_column(Text)
    fid_b: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), default="queue")
    area_m2: Mapped[float | None] = mapped_column(Double)
    outside_m: Mapped[float | None] = mapped_column(Double)
    reason: Mapped[str] = mapped_column(Text)

    # Evidence geometry: the intersection itself, in the storage CRS.
    geom: Mapped[Any | None] = mapped_column(
        Geometry(
            "GEOMETRY",
            srid=get_settings().storage_srid,
            spatial_index=False,  # the gist index is created by migration 0004
            nullable=True,
        )
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default="now()"
    )

    def __repr__(self) -> str:
        return f"<Conflict {self.conflict_id} {self.type}/{self.severity} {self.state}>"


class ConflictDecision(Base):
    """Append-only log of reviewer actions on a conflict."""

    __tablename__ = "conflict_decision"

    __table_args__ = (Index("ix_conflict_decision_conflict", "conflict_id"),)

    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conflict_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String(32))
    reason_code: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default="now()"
    )

    def __repr__(self) -> str:
        return f"<ConflictDecision {self.decision_id} {self.action} {self.reason_code}>"


class FeatureMatch(Base):
    """One accepted 1-to-1 match between polygon features of two sources (plan Stage 4).

    `score` is the logistic scorer's output in [0, 1]; `method` records how the pair
    was assigned (`hungarian`, or a per-component greedy fallback). `pair_features`
    keeps the values the scorer saw, so the decision can be explained later. Matches
    carry no decision history yet: a re-run replaces the pair's rows whole.
    """

    __tablename__ = "feature_match"

    __table_args__ = (
        Index(
            "uq_feature_match_pair",
            "source_a",
            "source_b",
            "fid_a",
            "fid_b",
            unique=True,
        ),
        Index("ix_feature_match_source", "source_a"),
    )

    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_a: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_b: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fid_a: Mapped[str] = mapped_column(Text)
    fid_b: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Double)
    method: Mapped[str] = mapped_column(String(32))
    pair_features: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default="now()"
    )

    def __repr__(self) -> str:
        return f"<FeatureMatch {self.match_id} score={self.score:.3f} {self.method}>"
