"""MinIO / S3 object store client and readiness check.

Stage 1 stores COG, GeoPackage and CSV uploads here; Stage 0 only proves the
store is reachable and the bucket exists.
"""

import time

from minio import Minio

from app.core.config import get_settings

settings = get_settings()

_RETRY_INTERVAL_SECONDS = 2.0


def get_object_store() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def check_object_store(warmup_seconds: float | None = None) -> dict[str, object]:
    """Probe the bucket, keeping the request open while a cold store boots.

    Render's free-tier MinIO sleeps when idle and needs ~40-50 s to start; the
    client itself gives up within seconds, so a single attempt reports DOWN for
    every page load after an idle period. Re-probing until `warmup_seconds`
    elapses lets one held request ride out the boot. The budget comes from
    OBJECTSTORE_WARMUP_SECONDS (0 disables), which tests set to 0.
    """
    budget = settings.objectstore_warmup_seconds if warmup_seconds is None else warmup_seconds
    deadline = time.monotonic() + max(budget, 0.0)
    last_error: str | None = None
    while True:
        try:
            exists = get_object_store().bucket_exists(settings.minio_bucket)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if not exists:
                return {"ok": False, "error": f"bucket does not exist: {settings.minio_bucket}"}
            return {"ok": True, "bucket": settings.minio_bucket}
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"ok": False, "error": last_error or "object store unreachable"}
        time.sleep(min(_RETRY_INTERVAL_SECONDS, remaining))
