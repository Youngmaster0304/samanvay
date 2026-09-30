"""Liveness and readiness endpoints.

/healthz answers "is this process up". /readyz answers "can it do its job", checking
PostGIS, Redis, the object store and the loaded NAKSHA policy, and returns 503 until
every check passes.
"""

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.objectstore import check_object_store
from app.core.policy import PolicyError, get_policy
from app.core.redis import check_redis
from app.db.session import check_database

router = APIRouter(tags=["health"])


def _policy_check() -> dict[str, object]:
    settings = get_settings()
    try:
        bundle = get_policy(settings.policy_path)
    except PolicyError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "name": bundle.name, "version": bundle.version, "path": bundle.path}


@router.get("/healthz", summary="Liveness probe")
def healthz() -> dict[str, object]:
    settings = get_settings()
    return {
        "service": "samanvay-api",
        "status": "ok",
        "version": settings.app_version,
        "env": settings.app_env,
        "storage_srid": settings.storage_srid,
    }


@router.get("/readyz", summary="Readiness probe with dependency detail")
def readyz() -> Response:
    settings = get_settings()
    checks = {
        "database": check_database(),
        "redis": check_redis(settings.check_timeout_seconds),
        "object_store": check_object_store(),
        "policy": _policy_check(),
    }
    ready = all(bool(check.get("ok")) for check in checks.values())
    body = {
        "service": "samanvay-api",
        "status": "ready" if ready else "not_ready",
        "version": settings.app_version,
        "checks": checks,
    }
    return JSONResponse(content=body, status_code=200 if ready else 503)
