"""Conflict endpoints (backend.md §5.6, plan Stage 6 first slice).

- `POST /conflicts/detect`   compares two loaded sources and queues what they disagree about.
- `GET  /conflicts`          the reviewer queue, filterable by state and type.
- `POST /conflicts/{id}/decision`  accept A / accept B / defer / reject, with a reason code;
  decisions are append-only.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.conflicts import service as conflicts_service
from app.core.config import get_settings
from app.core.policy import PolicyBundle, get_policy
from app.db.session import get_session
from app.ingest.errors import IngestError

router = APIRouter(prefix="/conflicts", tags=["conflicts"])

SessionDep = Annotated[Session, Depends(get_session)]


def _policy_bundle() -> PolicyBundle:
    return get_policy(get_settings().policy_path)


PolicyDep = Annotated[PolicyBundle, Depends(_policy_bundle)]


class DetectIn(BaseModel):
    source_a: UUID
    source_b: UUID


class DecisionIn(BaseModel):
    action: Literal["accept_a", "accept_b", "defer", "reject"]
    reason_code: str = Field(min_length=1, max_length=64)
    actor: str = Field(default="reviewer", min_length=1, max_length=64)


def _refuse(exc: IngestError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.as_detail())


@router.post(
    "/detect",
    summary="Detect geometric conflicts between two loaded sources",
    status_code=201,
)
def post_detect(body: DetectIn, session: SessionDep, policy: PolicyDep) -> dict[str, Any]:
    try:
        return conflicts_service.detect_conflicts(
            session, body.source_a, body.source_b, policy=policy
        )
    except IngestError as exc:
        raise _refuse(exc) from exc


@router.get("", summary="List conflicts (the reviewer queue)")
def get_conflicts(
    session: SessionDep,
    state: Annotated[str | None, Query(max_length=32)] = None,
    type: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    return conflicts_service.list_conflicts(session, state=state, conflict_type=type, limit=limit)


@router.post(
    "/{conflict_id}/decision",
    summary="Record a reviewer decision on a conflict (append-only)",
)
def post_decision(conflict_id: UUID, body: DecisionIn, session: SessionDep) -> dict[str, Any]:
    try:
        return conflicts_service.decide_conflict(
            session,
            conflict_id,
            action=body.action,
            reason_code=body.reason_code,
            actor=body.actor,
        )
    except IngestError as exc:
        raise _refuse(exc) from exc
