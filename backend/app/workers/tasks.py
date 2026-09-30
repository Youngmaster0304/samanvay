"""Celery tasks. Pipeline stages are added from Stage 1 onwards."""

from typing import Any

from app.workers.celery_app import celery_app


@celery_app.task(name="samanvay.ping")
def ping() -> dict[str, Any]:
    return {"ok": True, "service": "samanvay-worker"}
