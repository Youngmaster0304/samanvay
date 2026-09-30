"""Object store used by ingest: the original bytes, addressed by their checksum."""

from __future__ import annotations

from typing import BinaryIO, Protocol

from app.core.config import get_settings
from app.core.objectstore import get_object_store


class ObjectStore(Protocol):
    """`put` for ingest (identity comes from the registry row); `get` to read bytes back."""

    def put(self, key: str, stream: BinaryIO, length: int, *, content_type: str) -> None:
        """Store exactly `length` bytes from `stream` under `key`."""
        ...

    def get(self, key: str) -> bytes:
        """Read every byte stored under `key`; raises an error when the key is absent."""
        ...


class MinioObjectStore:
    def __init__(self, bucket: str) -> None:
        self._bucket = bucket
        self._client = get_object_store()

    def put(self, key: str, stream: BinaryIO, length: int, *, content_type: str) -> None:
        self._client.put_object(
            self._bucket,
            key,
            stream,
            length,
            content_type=content_type,
        )

    def get(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()


def get_store() -> ObjectStore:
    """Store used by the API; overridable in tests via FastAPI dependency overrides."""
    return MinioObjectStore(get_settings().minio_bucket)
