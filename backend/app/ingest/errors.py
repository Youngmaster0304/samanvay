"""Ingest errors carry a stable code, a human message and an HTTP status.

The API layer converts them into responses. Stage 8 will wrap the same payload in an
RFC 7807 problem document; keeping the code/message pair here means that change touches
one place.
"""

from __future__ import annotations


class IngestError(Exception):
    """A refusal that the caller can act on. Never raised for internal faults."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def as_detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}
