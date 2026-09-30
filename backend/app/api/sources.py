"""Registering a source, and reading the registry back.

`POST /sources` is the one write endpoint at Stage 1. It is idempotent twice over: by
`Idempotency-Key` when the client sends one, and by content, because the same bytes and
the same kind already have exactly one row (`backend.md` §5.1). A repeated upload
returns that row with `reused: true` and status 200 instead of a second record.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import SourceFeature, SourceRegistry
from app.db.session import get_session
from app.ingest.errors import IngestError
from app.ingest.preview import PreviewError, preview_info, preview_png
from app.ingest.service import IngestResult, ingest_upload, summarize
from app.ingest.store import ObjectStore, get_store

router = APIRouter(prefix="/sources", tags=["sources"])

SessionDep = Annotated[Session, Depends(get_session)]
StoreDep = Annotated[ObjectStore, Depends(get_store)]


class SourceOut(BaseModel):
    """One registered source, exactly as ingest recorded it."""

    source_id: str
    name: str
    kind: str
    format: str
    authority: str | None = None
    licence: str
    url: str | None = None
    vintage: str | None = None
    is_synthetic: bool
    sigma_m: float | None = None
    sha256: str
    size_bytes: int
    object_key: str
    crs: str | None = Field(description="CRS the source was registered under, or null")
    crs_source: str
    crs_original: str | None = None
    crs_declared: str | None = None
    has_geometry: bool
    feature_count: int | None = None
    coverage: list[float] | None = None
    attributes: list[str] = Field(default_factory=list)
    geometry_types: list[str] = Field(default_factory=list)
    layer: str | None = None
    layers: list[str] = Field(default_factory=list)
    raster: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)
    ingested_at: str | None = None
    reused: bool = False
    reuse_reason: str | None = None


class SourceListOut(BaseModel):
    items: list[SourceOut]
    total: int


def _stored(row: SourceRegistry) -> SourceOut:
    """A row read back from the database; `reused` only means something to a writer."""
    payload = summarize(IngestResult(row=row, reused=False, reuse_reason=None))
    return SourceOut(**payload)


def _refuse(exc: IngestError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.as_detail())


@router.post(
    "",
    response_model=SourceOut,
    status_code=201,
    summary="Upload and register a source",
    responses={200: {"description": "these bytes were already registered"}},
)
def create_source(
    response: Response,
    session: SessionDep,
    store: StoreDep,
    file: Annotated[UploadFile, File(description="GeoTIFF, GeoJSON, GeoPackage, shapefile or CSV")],
    name: Annotated[str, Form(min_length=1)],
    kind: Annotated[str, Form(description="drone_ori | cadastral | revenue | ...")],
    licence: Annotated[str, Form(min_length=1)],
    authority: Annotated[str | None, Form()] = None,
    url: Annotated[str | None, Form()] = None,
    vintage: Annotated[date | None, Form()] = None,
    sigma_m: Annotated[float | None, Form(ge=0)] = None,
    is_synthetic: Annotated[bool, Form()] = False,
    declared_crs: Annotated[str | None, Form(description="e.g. EPSG:32646")] = None,
    layer: Annotated[str | None, Form(description="layer to inspect in a multi-layer file")] = None,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", description="client-supplied replay key")
    ] = None,
) -> SourceOut:
    try:
        result = ingest_upload(
            filename=file.filename or "",
            stream=file.file,
            name=name,
            kind=kind,
            licence=licence,
            authority=authority,
            url=url,
            vintage=vintage,
            is_synthetic=is_synthetic,
            sigma_m=sigma_m,
            declared_crs=declared_crs,
            layer=layer,
            client_key=idempotency_key,
            session=session,
            store=store,
            settings=get_settings(),
        )
    except IngestError as exc:
        raise _refuse(exc) from exc

    if result.reused:
        response.status_code = 200
    return SourceOut(**summarize(result))


@router.get("", response_model=SourceListOut, summary="List registered sources")
def list_sources(
    session: SessionDep,
    kind: Annotated[str | None, Query(description="filter to one source kind")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SourceListOut:
    count_query = select(func.count()).select_from(SourceRegistry)
    if kind is not None:
        count_query = count_query.where(SourceRegistry.kind == kind)
    total = int(session.execute(count_query).scalar_one())

    items_query = select(SourceRegistry).order_by(SourceRegistry.ingested_at.desc())
    if kind is not None:
        items_query = items_query.where(SourceRegistry.kind == kind)
    items = session.execute(items_query.limit(limit).offset(offset)).scalars().all()

    return SourceListOut(items=[_stored(row) for row in items], total=total)


@router.get(
    "/{source_id}/features.geojson",
    summary="Loaded features of one source as GeoJSON in WGS 84",
    response_class=Response,
)
def source_features_geojson(
    source_id: UUID,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50_000, description="cap the response size")] = 20_000,
) -> Response:
    """What the map draws: the stored features, reprojected to EPSG:4326 on read.

    Sources that were registered but never loaded (rasters, geometry-less tables)
    answer with an empty collection rather than an error, so a client can probe
    every registry row the same way.
    """
    row = session.get(SourceRegistry, source_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "source_not_found", "message": f"no source {source_id}"},
        )

    total = int(
        session.execute(
            select(func.count())
            .select_from(SourceFeature)
            .where(SourceFeature.source_id == source_id)
        ).scalar_one()
    )
    rows = session.execute(
        select(
            SourceFeature.source_fid,
            SourceFeature.feature_class,
            SourceFeature.extractor_conf,
            SourceFeature.qc_flags,
            SourceFeature.raw_props,
            func.ST_AsGeoJSON(func.ST_Transform(SourceFeature.geom, 4326)),
        )
        .where(SourceFeature.source_id == source_id)
        .order_by(SourceFeature.source_fid)
        .limit(limit)
    ).all()

    features = [
        {
            "type": "Feature",
            "id": fid,
            "geometry": json.loads(geometry),
            "properties": {
                "feature_class": feature_class,
                "extractor_conf": extractor_conf,
                "qc_flags": flags or [],
                "props": raw_props or {},
            },
        }
        for fid, feature_class, extractor_conf, flags, raw_props, geometry in rows
    ]
    payload: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
        "total": total,
        "source": {"source_id": str(row.source_id), "name": row.name, "kind": row.kind},
    }
    if total > len(features):
        payload["truncated"] = True
    return Response(content=json.dumps(payload), media_type="application/geo+json")


def _require_row(session: Session, source_id: UUID) -> SourceRegistry:
    row = session.get(SourceRegistry, source_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "source_not_found", "message": f"no source {source_id}"},
        )
    return row


def _stored_bytes(row: SourceRegistry, store: ObjectStore) -> bytes:
    try:
        return store.get(row.object_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "preview_bytes_missing",
                "message": "the stored bytes are gone (object storage was reset); "
                "re-upload the file",
            },
        ) from exc


@router.get(
    "/{source_id}/preview",
    summary="WGS 84 placement of a raster preview",
)
def source_preview(
    source_id: UUID,
    session: SessionDep,
    store: StoreDep,
) -> dict[str, Any]:
    row = _require_row(session, source_id)
    if row.raster is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "no_preview", "message": "only rasters have a preview"},
        )
    try:
        info = preview_info(_stored_bytes(row, store))
    except PreviewError as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": exc.message}
        ) from exc
    return {
        "source_id": str(row.source_id),
        "name": row.name,
        "bounds": info["bounds"],
        "width": info["width"],
        "height": info["height"],
        "png": f"/sources/{row.source_id}/preview.png",
    }


@router.get(
    "/{source_id}/preview.png",
    summary="Downsampled RGB PNG of a raster source",
    response_class=Response,
)
def source_preview_png(
    source_id: UUID,
    session: SessionDep,
    store: StoreDep,
) -> Response:
    row = _require_row(session, source_id)
    if row.raster is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "no_preview", "message": "only rasters have a preview"},
        )
    try:
        png = preview_png(_stored_bytes(row, store))
    except PreviewError as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": exc.message}
        ) from exc
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{source_id}", response_model=SourceOut, summary="Read one source")
def get_source(
    source_id: UUID,
    session: SessionDep,
) -> SourceOut:
    row = session.get(SourceRegistry, source_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "source_not_found", "message": f"no source {source_id}"},
        )
    return _stored(row)
