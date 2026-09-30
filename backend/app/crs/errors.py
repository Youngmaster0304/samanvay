"""Refusals raised by the CRS engine, shaped like the ingest ones.

They subclass `IngestError` so the API's single error handler can convert any refusal
into a `{code, message}` detail with a status, while callers still see a name that
matches where the check happened.
"""

from __future__ import annotations

from app.ingest.errors import IngestError


class CrsError(IngestError):
    """A refusal from the CRS engine: bad control points, missing source, unusable fit."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(code, message, status=status)
