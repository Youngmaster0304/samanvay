"""Matching endpoints (plan Stage 4).

- `POST /matches/detect`  score and assign 1-to-1 polygon matches between two
  loaded sources (radius blocking, logistic scorer, Hungarian assignment).
- `POST /matches/offset`  estimate (and optionally apply) the translation that
  aligns source B onto source A; applying writes a linked corrected copy.
- `GET  /matches`         the accepted matches, filterable by source, each with
  the pair features that justified it.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.policy import PolicyBundle, get_policy
from app.db.session import get_session
from app.ingest.errors import IngestError
from app.matching import offset as offset_service
from app.matching import service as matching_service

router = APIRouter(prefix="/matches", tags=["matches"])

SessionDep = Annotated[Session, Depends(get_session)]


def _policy_bundle() -> PolicyBundle:
    return get_policy(get_settings().policy_path)


PolicyDep = Annotated[PolicyBundle, Depends(_policy_bundle)]


class DetectIn(BaseModel):
    source_a: UUID
    source_b: UUID


class OffsetIn(BaseModel):
    source_a: UUID
    source_b: UUID
    apply: bool = False


def _refuse(exc: IngestError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.as_detail())


@router.post(
    "/detect",
    summary="Score and assign 1-to-1 polygon matches between two loaded sources",
    status_code=201,
)
def post_detect(body: DetectIn, session: SessionDep, policy: PolicyDep) -> dict[str, Any]:
    try:
        return matching_service.detect_matches(session, body.source_a, body.source_b, policy=policy)
    except IngestError as exc:
        raise _refuse(exc) from exc


@router.post(
    "/offset",
    summary="Estimate the translation that aligns source B onto source A",
)
def post_offset(body: OffsetIn, session: SessionDep, policy: PolicyDep) -> dict[str, Any]:
    try:
        return offset_service.estimate_offset(
            session, body.source_a, body.source_b, policy=policy, apply=body.apply
        )
    except IngestError as exc:
        raise _refuse(exc) from exc


@router.get("", summary="List accepted feature matches")
def get_matches(
    session: SessionDep,
    source: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    return matching_service.list_matches(session, source=source, limit=limit)
