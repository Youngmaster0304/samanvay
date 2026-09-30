"""MinIO / S3 object store client and readiness check.

Stage 1 stores COG, GeoPackage and CSV uploads here; Stage 0 only proves the
store is reachable and the bucket exists.
"""

from minio import Minio

from app.core.config import get_settings

settings = get_settings()


def get_object_store() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def check_object_store() -> dict[str, object]:
    try:
        exists = get_object_store().bucket_exists(settings.minio_bucket)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if not exists:
        return {"ok": False, "error": f"bucket does not exist: {settings.minio_bucket}"}
    return {"ok": True, "bucket": settings.minio_bucket}
