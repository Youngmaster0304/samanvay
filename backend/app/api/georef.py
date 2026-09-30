"""Georeferencing and feature loading endpoints (backend.md §5.2, plan Stage 2).

- `POST /sources/{id}/georef` fits the rubber-sheeting ladder to control pairs and stores
  the report (leave-one-out RMSE per candidate, per-point residuals, blunder flags).
- `GET  /sources/{id}/georef` returns the most recent fit, or 404 when there is none.
- `POST /sources/{id}/load` reprojects the registered bytes into the storage CRS, applies
  the fit when one exists, and upserts `source_feature` rows.
- `GET  /sources/{id}/health` reports CRS, transform history and what is loaded.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.policy import PolicyBundle, get_policy
from app.crs import service as crs_service
from app.db.session import get_session
from app.ingest.errors import IngestError
from app.ingest.store import ObjectStore, get_store

router = APIRouter(prefix="/sources", tags=["georeferencing"])

SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[ObjectStore, Depends(get_store)]


def _policy_bundle() -> PolicyBundle:
    return get_policy(get_settings().policy_path)


PolicyDep = Annotated[PolicyBundle, Depends(_policy_bundle)]


class ControlPair(BaseModel):
    """One control pair: the as-registered position and the true ground position."""

    model_config = ConfigDict(populate_by_name=True)

    source: list[float] = Field(
        alias="from",
        min_length=2,
        max_length=2,
        description="[x, y] as the source currently maps it, in the coordinate unit given below",
    )
    target: list[float] = Field(
        alias="to",
        min_length=2,
        max_length=2,
        description="[x, y] of the same point on the ground (surveyed or authoritative)",
    )
    label: str | None = Field(default=None, description="corner or marker name, for the report")


class GeorefIn(BaseModel):
    pairs: list[ControlPair] = Field(min_length=1, max_length=500)
    unit: str = Field(
        default="m",
        description="unit the control coordinates are in; thresholds are interpreted in it",
    )


class GeorefReportOut(BaseModel):
    model: str
    n_control: int
    unit: str
    models: list[dict[str, Any]]
    rmse: float
    loo_rmse: float | None = None
    max_residual: float
    blunder_threshold: float
    blunders: list[dict[str, Any]]
    residuals: list[dict[str, Any]]
    params: dict[str, Any]
    policy: dict[str, Any]
    pipeline: str | None = None
    created_at: str | None = None
    transform_log_id: str | None = None
    source_id: str | None = None


def _refuse(exc: IngestError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.as_detail())


@router.post(
    "/{source_id}/georef",
    response_model=GeorefReportOut,
    status_code=201,
    summary="Fit control-point georeferencing to a source",
)
def post_georef(
    source_id: UUID,
    body: GeorefIn,
    session: SessionDep,
    policy: PolicyDep,
) -> dict[str, Any]:
    pairs = [pair.model_dump(by_alias=True) for pair in body.pairs]
    try:
        return crs_service.fit_georef(session, source_id, pairs, policy=policy, unit=body.unit)
    except IngestError as exc:
        raise _refuse(exc) from exc


@router.get(
    "/{source_id}/georef",
    response_model=GeorefReportOut,
    summary="Read the latest control-point fit for a source",
)
def get_georef(source_id: UUID, session: SessionDep) -> dict[str, Any]:
    try:
        report = crs_service.latest_georef(session, source_id)
    except IngestError as exc:
        raise _refuse(exc) from exc
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "no_georef",
                "message": f"source {source_id} has no control-point fit yet",
            },
        )
    return report


@router.post(
    "/{source_id}/load",
    summary="Load a source into the storage CRS (reproject, apply any fit, upsert rows)",
)
def post_load(
    source_id: UUID,
    session: SessionDep,
    store: StoreDep,
) -> dict[str, Any]:
    try:
        return crs_service.load_features(session, store, source_id, settings=get_settings())
    except IngestError as exc:
        raise _refuse(exc) from exc


@router.get("/{source_id}/health", summary="CRS, transform history and loaded features")
def get_health(source_id: UUID, session: SessionDep) -> dict[str, Any]:
    try:
        return crs_service.source_health(session, source_id, settings=get_settings())
    except IngestError as exc:
        raise _refuse(exc) from exc
