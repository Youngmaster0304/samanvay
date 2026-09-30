"""SHA-256 of a file, streamed.

The checksum is the identity of a source: `backend.md` §5.1 requires one row per file
with its checksum, and the same hash means the same bytes means an idempotent
re-ingest.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

_CHUNK = 1 << 20  # 1 MiB


def hash_stream(stream: BinaryIO, *, chunk_size: int = _CHUNK) -> str:
    """Hex SHA-256 of everything left in `stream`, read in bounded chunks."""
    digest = hashlib.sha256()
    while chunk := stream.read(chunk_size):
        digest.update(chunk)
    return digest.hexdigest()


def hash_file(path: str | Path) -> str:
    with open(path, "rb") as handle:
        return hash_stream(handle)
