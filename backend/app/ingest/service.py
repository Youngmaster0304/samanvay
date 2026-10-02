"""Ingest: one uploaded file in, one provenance row out.

The order of operations is deliberate and matches `backend.md` §5.1:

    bound the bytes -> hash -> idempotency -> detect -> unpack -> inspect -> CRS
    -> kind/format rules -> store the bytes -> register

Every step that can refuse does so with a code the API returns to the operator, and
nothing is repaired silently: a missing CRS, an ambiguous bundle and a mismatched magic
number are all reported rather than guessed around.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, BinaryIO
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import SourceRegistry, utcnow
from app.domain.sources import SourceKind, allowed_formats_for
from app.ingest.archive import unpack_archive
from app.ingest.checksums import hash_file
from app.ingest.connectors import inspect_payload
from app.ingest.connectors.base import RasterInfo
from app.ingest.crs import CrsDecision, resolve_crs
from app.ingest.detect import detect_format, is_archive, read_header
from app.ingest.errors import IngestError
from app.ingest.store import ObjectStore

_UPLOAD_CONTENT_TYPES: dict[str, str] = {
    ".zip": "application/zip",
    ".csv": "text/csv",
    ".geojson": "application/geo+json",
    ".json": "application/geo+json",
    ".gpkg": "application/geopackage+sqlite3",
    ".shp": "application/vnd.shapefile",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}

_CHUNK = 1 << 20  # 1 MiB


@dataclass(frozen=True)
class IngestResult:
    """The registry row plus what made this call return the row it did."""

    row: SourceRegistry
    reused: bool
    reuse_reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return summarize(self)


def summarize(result: IngestResult) -> dict[str, Any]:
    """The API shape for one source: flat fields, straight from the row.

    `crs` is the CRS the source was registered under, or null for a table with no
    geometry. It is never filled in with a default.
    """
    row = result.row
    return {
        "source_id": str(row.source_id),
        "name": row.name,
        "kind": row.kind,
        "format": row.format,
        "authority": row.authority,
        "licence": row.licence,
        "url": row.url,
        "vintage": row.vintage.isoformat() if row.vintage else None,
        "is_synthetic": row.is_synthetic,
        "sigma_m": row.sigma_m,
        "sha256": row.sha256,
        "size_bytes": row.size_bytes,
        "object_key": row.object_key,
        "crs": row.crs_used,
        "crs_source": row.crs_source,
        "crs_original": row.crs_original,
        "crs_declared": row.crs_declared,
        "has_geometry": row.has_geometry,
        "feature_count": row.feature_count,
        "coverage": row.coverage,
        "attributes": row.attributes,
        "geometry_types": row.geometry_types,
        "layer": row.layer,
        "layers": row.layers,
        "raster": row.raster,
        "notes": row.notes,
        "ingested_at": _iso(row.ingested_at),
        "reused": result.reused,
        "reuse_reason": result.reuse_reason,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _spool(stream: BinaryIO, target: Path, *, limit: int) -> int:
    """Copy `stream` to `target`, refusing anything over `limit` bytes."""
    written = 0
    with open(target, "wb") as handle:
        while chunk := stream.read(_CHUNK):
            written += len(chunk)
            if written > limit:
                handle.close()
                target.unlink(missing_ok=True)
                raise IngestError(
                    "upload_too_large",
                    f"the upload exceeds {limit} bytes; split the dataset or raise "
                    "MAX_UPLOAD_BYTES",
                    status=413,
                )
            handle.write(chunk)
    if written == 0:
        raise IngestError("empty_file", "the uploaded file contains no data", status=422)
    return written


def _safe_upload_name(filename: str) -> str:
    """Keep only the basename of an operator-supplied filename."""
    name = Path(filename.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        raise IngestError("invalid_filename", "the upload needs a non-empty filename")
    return name


def _find_existing(
    session: Session, *, client_key: str | None, sha256: str, kind: str
) -> SourceRegistry | None:
    if client_key:
        existing = session.execute(
            select(SourceRegistry).where(SourceRegistry.client_key == client_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    return session.execute(
        select(SourceRegistry).where(SourceRegistry.sha256 == sha256, SourceRegistry.kind == kind)
    ).scalar_one_or_none()


def ingest_upload(
    *,
    filename: str,
    stream: BinaryIO,
    name: str,
    kind: str,
    licence: str,
    authority: str | None = None,
    url: str | None = None,
    vintage: date | None = None,
    is_synthetic: bool = False,
    sigma_m: float | None = None,
    declared_crs: str | None = None,
    layer: str | None = None,
    client_key: str | None = None,
    session: Session,
    store: ObjectStore,
    settings: Settings | None = None,
) -> IngestResult:
    """Register one upload and return the row that now describes it."""
    cfg = settings or get_settings()

    try:
        source_kind = SourceKind(kind)
    except ValueError as exc:
        known_kinds = ", ".join(member.value for member in SourceKind)
        raise IngestError(
            "unknown_kind",
            f"{kind!r} is not a source kind; expected one of: {known_kinds}",
        ) from exc

    if not name.strip():
        raise IngestError("missing_name", "the source needs a name")
    if not licence.strip():
        raise IngestError(
            "missing_licence",
            "the source needs a licence; provenance without a licence cannot be published",
        )

    upload_name = _safe_upload_name(filename)
    key = client_key.strip() if client_key and client_key.strip() else None

    with TemporaryDirectory(prefix="samanvay-ingest-") as tmp:
        workdir = Path(tmp)
        original = workdir / upload_name
        _spool(stream, original, limit=cfg.max_upload_bytes)

        sha256 = hash_file(original)

        existing = _find_existing(session, client_key=key, sha256=sha256, kind=source_kind.value)
        if existing is not None:
            reason = "idempotency_key" if key and existing.client_key == key else "same_sha256"
            # The store is ephemeral on the demo host: a redeploy can empty the
            # bucket while the registry rows survive. Reuse must then restore the
            # bytes too, otherwise the row keeps pointing at nothing.
            if not store.exists(existing.object_key):
                content_type = _UPLOAD_CONTENT_TYPES.get(Path(upload_name).suffix.lower(), "")
                with open(original, "rb") as handle:
                    store.put(
                        existing.object_key,
                        handle,
                        original.stat().st_size,
                        content_type=content_type,
                    )
            return IngestResult(row=existing, reused=True, reuse_reason=reason)

        payload = original
        extra_notes: list[str] = []
        if is_archive(upload_name, read_header(original)):
            unpacked = unpack_archive(
                original,
                workdir / "unpacked",
                max_entries=cfg.max_archive_entries,
                max_bytes=cfg.max_archive_bytes,
            )
            payload = unpacked.payload
            extra_notes.append(
                f"archive unpacked: {len(unpacked.members)} files, payload {payload.name}"
            )

        fmt = detect_format(payload.name, read_header(payload))
        inspection = inspect_payload(payload, fmt, layer=layer)

        allowed = allowed_formats_for(source_kind)
        if allowed is not None and fmt not in allowed:
            expect = ", ".join(sorted(member.value for member in allowed))
            raise IngestError(
                "format_not_allowed_for_kind",
                f"{source_kind.value} accepts {expect}, not {fmt.value}",
            )

        decision: CrsDecision = resolve_crs(
            file_crs=inspection.crs,
            file_crs_hint=inspection.crs_hint,
            declared_crs=declared_crs,
            has_geometry=inspection.has_geometry,
        )

        object_key = f"sources/{sha256[:2]}/{sha256}/{upload_name}"
        content_type = _UPLOAD_CONTENT_TYPES.get(Path(upload_name).suffix.lower(), "")
        with open(original, "rb") as handle:
            store.put(object_key, handle, original.stat().st_size, content_type=content_type)

        notes = [*extra_notes, *inspection.notes]
        if decision.source.value == "declared" and decision.from_file is None:
            notes.append(
                f"coordinate reference system {decision.crs} was supplied by the operator "
                "and not read from the file"
            )

        row = SourceRegistry(
            source_id=uuid4(),
            name=name.strip(),
            kind=source_kind.value,
            authority=authority.strip() if authority and authority.strip() else None,
            licence=licence.strip(),
            url=url.strip() if url and url.strip() else None,
            vintage=vintage,
            is_synthetic=is_synthetic,
            sigma_m=sigma_m,
            sha256=sha256,
            size_bytes=original.stat().st_size,
            object_key=object_key,
            client_key=key,
            format=fmt.value,
            crs_original=decision.from_file,
            crs_declared=decision.declared,
            crs_used=decision.crs,
            crs_source=decision.source.value,
            has_geometry=inspection.has_geometry,
            feature_count=inspection.feature_count,
            coverage=list(inspection.coverage) if inspection.coverage else None,
            attributes=inspection.attributes,
            geometry_types=inspection.geometry_types,
            layer=inspection.layer,
            layers=inspection.layers,
            raster=_raster_dict(inspection.raster),
            notes=notes,
            ingested_at=utcnow(),
        )

        try:
            session.add(row)
            session.commit()
        except IntegrityError:
            # Two uploads of the same bytes raced; the other one won, and its row is
            # the single record of these bytes.
            session.rollback()
            raced = _find_existing(session, client_key=key, sha256=sha256, kind=source_kind.value)
            if raced is None:
                raise
            return IngestResult(row=raced, reused=True, reuse_reason="same_sha256")

        _auto_load(session, store, row, cfg)
        return IngestResult(row=row, reused=False, reuse_reason=None)


def _auto_load(session: Session, store: ObjectStore, row: SourceRegistry, cfg: Settings) -> None:
    """Load the source's features straight after registration.

    Best effort by design: the ingest has already succeeded, so a load that cannot read
    the bytes or has no CRS is recorded as a registry note rather than turning a good
    upload into an error. The operator can always retry with `POST /sources/{id}/load`.
    """
    from app.crs.service import load_features  # the CRS engine builds on ingest, not vice versa

    try:
        summary = load_features(session, store, row.source_id, settings=cfg)
    except Exception as exc:
        session.rollback()
        row.notes = [*row.notes, f"feature load failed: {exc}"]
        session.commit()
        return

    if summary.get("loaded"):
        by_class = ", ".join(f"{name}={count}" for name, count in summary["by_class"].items())
        note = (
            f"loaded {summary['loaded']} features into storage CRS EPSG:{summary['storage_srid']}"
        )
        if by_class:
            note += f" ({by_class})"
        if summary.get("georef_applied"):
            note += " after control-point georeferencing"
        row.notes = [*row.notes, note]
    else:
        row.notes = [
            *row.notes,
            f"feature load skipped: {summary.get('skipped')} ({summary.get('reason')})",
        ]
    session.commit()


def _raster_dict(raster: RasterInfo | None) -> dict[str, Any] | None:
    if raster is None:
        return None
    return {
        "driver": raster.driver,
        "width": raster.width,
        "height": raster.height,
        "bands": raster.bands,
        "dtypes": raster.dtypes,
        "resolution": list(raster.resolution),
        "overviews": raster.overviews,
        "is_cog": raster.is_cog,
        "cog_checks": raster.cog_checks,
    }
