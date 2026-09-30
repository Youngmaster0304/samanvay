"""Redis readiness check (Celery broker and result backend)."""

from redis import Redis

from app.core.config import get_settings

settings = get_settings()


def check_redis(timeout_seconds: float) -> dict[str, object]:
    client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=timeout_seconds,
        socket_timeout=timeout_seconds,
    )
    try:
        client.ping()
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        client.close()
    return {"ok": True}
