"""Process-wide GDAL limits applied before any file is opened.

These are operational guard rails, not policy thresholds: they bound what GDAL is
allowed to touch during a single ingest. True isolation (a sandboxed worker process)
is deferred to the security pass in `backend.md` §7.
"""

from __future__ import annotations

import os

GDAL_LIMITS: dict[str, str] = {
    # Do not walk the directory next to the file: uploads arrive as single files.
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    # A bare .shp upload has no .shx sibling; let GDAL rebuild the index.
    "SHAPE_RESTORE_SHX": "YES",
    # Never write .aux.xml sidecars next to an upload.
    "GDAL_PAM_ENABLED": "NO",
    # Bound the block cache and any network access a datasource might attempt.
    "GDAL_CACHEMAX": "64",
    "GDAL_HTTP_TIMEOUT": "5",
    "GDAL_HTTP_CONNECTTIMEOUT": "5",
    "GDAL_NUM_THREADS": "1",
}

_applied = False


def apply_gdal_limits() -> None:
    """Apply the limits once per process. Idempotent."""
    global _applied
    if _applied:
        return
    for key, value in GDAL_LIMITS.items():
        os.environ.setdefault(key, value)
    _applied = True
