"""CRS normalisation and the rules for deciding a source's CRS.

`backend.md` §5.1: validate the CRS, reject files that carry none unless the operator
supplies one explicitly, and log that choice. Every decision lands in the source's
summary as `crs: {from_file, declared, used, source}`.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyproj import CRS
from pyproj.exceptions import CRSError

from app.domain.sources import CrsSource
from app.ingest.errors import IngestError


@dataclass(frozen=True)
class CrsDecision:
    """The CRS a source will be registered under, and where it came from."""

    crs: str | None
    source: CrsSource
    from_file: str | None
    declared: str | None


def as_crs(raw: str, *, origin: str) -> CRS:
    """Parse `raw` into a pyproj CRS or refuse with an actionable message."""
    try:
        return CRS.from_user_input(raw)
    except CRSError as exc:
        raise IngestError(
            "invalid_crs",
            f"{origin}: {raw!r} is not a coordinate reference system pyproj recognises",
        ) from exc


def normalize_crs(raw: str, *, origin: str) -> str:
    """Authority string when one exists (EPSG:32646), else the CRS name."""
    crs = as_crs(raw, origin=origin)
    authority = crs.to_authority()
    if authority is not None:
        return f"{authority[0]}:{authority[1]}"
    return crs.name


def resolve_crs(
    *,
    file_crs: str | None,
    file_crs_hint: CrsSource,
    declared_crs: str | None,
    has_geometry: bool,
) -> CrsDecision:
    """Decide the CRS for one source.

    - No geometry (a record-of-rights table): CRS does not apply, and declaring one is
      an error rather than something to ignore silently.
    - Geometry and no CRS: refuse unless `declared_crs` is supplied.
    - Both present and different: refuse; a file's CRS is never overridden silently.
    """
    declared = declared_crs.strip() if declared_crs and declared_crs.strip() else None

    if not has_geometry:
        if declared is not None:
            raise IngestError(
                "crs_not_applicable",
                "this file has no geometry, so declared_crs does not apply; "
                "remove declared_crs or upload the spatial version of this dataset",
            )
        return CrsDecision(crs=None, source=CrsSource.NONE, from_file=None, declared=None)

    from_file: str | None = None
    if file_crs is not None:
        from_file = normalize_crs(file_crs, origin="file")

    declared_normalized: str | None = None
    if declared is not None:
        declared_normalized = normalize_crs(declared, origin="declared_crs")

    # An assumed CRS is never a conflict and never wins: a latitude/longitude pair read
    # from a CSV implies WGS 84, but the operator's explicit declaration says otherwise,
    # and an explicit statement beats an implication. The implied value is still reported
    # through `from_file` so the summary records what the assumption was.
    if file_crs_hint is CrsSource.IMPLICIT_WGS84 and declared_normalized is not None:
        return CrsDecision(
            crs=declared_normalized,
            source=CrsSource.DECLARED,
            from_file=file_crs,
            declared=declared_normalized,
        )

    if (
        from_file is not None
        and declared_normalized is not None
        and as_crs(from_file, origin="file") != as_crs(declared_normalized, origin="declared_crs")
    ):
        raise IngestError(
            "crs_conflict",
            f"the file reports {from_file} but declared_crs is {declared_normalized}; "
            "remove declared_crs, or correct the file, then upload again",
        )

    if declared_normalized is not None and from_file is None:
        return CrsDecision(
            crs=declared_normalized,
            source=CrsSource.DECLARED,
            from_file=None,
            declared=declared_normalized,
        )

    if from_file is not None:
        return CrsDecision(
            crs=from_file,
            source=file_crs_hint,
            from_file=from_file,
            declared=declared_normalized,
        )

    raise IngestError(
        "missing_crs",
        "this file carries no coordinate reference system and none was declared; "
        "resend it with declared_crs (for example EPSG:32646 or EPSG:4326). "
        "The choice is recorded in the source registry",
    )
