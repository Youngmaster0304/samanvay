"""Matching endpoints (plan Stage 4, first slice).

- `POST /matches/detect`  assign 1-to-1 polygon matches between two loaded sources.
- `GET  /matches`         the accepted matches, filterable by source.
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
from app.matching import service as matching_service

router = APIRouter(prefix="/matches", tags=["matches"])

SessionDep = Annotated[Session, Depends(get_session)]


def _policy_bundle() -> PolicyBundle:
    return get_policy(get_settings().policy_path)


PolicyDep = Annotated[PolicyBundle, Depends(_policy_bundle)]


class DetectIn(BaseModel):
    source_a: UUID
    source_b: UUID


def _refuse(exc: IngestError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.as_detail())


@router.post(
    "/detect",
    summary="Match polygon features of two loaded sources by IoU",
    status_code=201,
)
def post_detect(body: DetectIn, session: SessionDep, policy: PolicyDep) -> dict[str, Any]:
    try:
        return matching_service.detect_matches(session, body.source_a, body.source_b, policy=policy)
    except IngestError as exc:
        raise _refuse(exc) from exc


@router.get("", summary="List accepted feature matches")
def get_matches(
    session: SessionDep,
    source: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    return matching_service.list_matches(session, source=source, limit=limit)
