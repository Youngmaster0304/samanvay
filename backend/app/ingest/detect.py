"""Format detection: extension first, then magic bytes, then the CSV header.

Detection never trusts the filename alone, and never guesses: a file whose bytes
contradict its extension is refused with a code the caller can act on.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.sources import SourceFormat
from app.ingest.csv_columns import find_coordinate_columns
from app.ingest.errors import IngestError

HEADER_BYTES = 8192

MAGIC_GEOTIFF = frozenset({b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"})
MAGIC_SQLITE = b"SQLite format 3\x00"
MAGIC_ZIP = frozenset({b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"})
SHAPEFILE_CODE = 9994

EXTENSION_FORMATS: dict[str, SourceFormat] = {
    ".tif": SourceFormat.GEOTIFF,
    ".tiff": SourceFormat.GEOTIFF,
    ".geojson": SourceFormat.GEOJSON,
    ".json": SourceFormat.GEOJSON,
    ".gpkg": SourceFormat.GPKG,
    ".shp": SourceFormat.SHAPEFILE,
}


def read_header(path: Path, size: int = HEADER_BYTES) -> bytes:
    with open(path, "rb") as handle:
        return handle.read(size)


def is_archive(filename: str, header: bytes) -> bool:
    """True when the upload is a zip; the caller unpacks it before detecting again."""
    return Path(filename).suffix.lower() == ".zip" or header[:4] in MAGIC_ZIP


def _decode(header: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return header.decode(encoding)
        except UnicodeDecodeError:
            continue
    return header.decode("utf-8", errors="replace")


def _be_int(prefix: bytes) -> int:
    return int.from_bytes(prefix[:4], "big") if len(prefix) >= 4 else -1


def detect_format(filename: str, header: bytes) -> SourceFormat:
    """Return the format of the file `filename`, given its first bytes."""
    suffix = Path(filename).suffix.lower()

    if suffix == ".zip" or header[:4] in MAGIC_ZIP:
        raise IngestError(
            "unexpected_archive",
            "zips are unpacked before detection; this call should not see one",
        )

    expected = EXTENSION_FORMATS.get(suffix)
    if expected is None and suffix != ".csv":
        allowed = sorted({*EXTENSION_FORMATS, ".csv"})
        raise IngestError(
            "unsupported_extension",
            f"extension {suffix or '(none)'} is not one of {', '.join(allowed)}",
            status=415,
        )

    if expected is SourceFormat.GEOTIFF:
        if header[:4] not in MAGIC_GEOTIFF:
            raise _mismatch(filename, "a GeoTIFF header (II*/MM*)")
        return expected

    if expected is SourceFormat.GPKG:
        if header[: len(MAGIC_SQLITE)] != MAGIC_SQLITE:
            raise _mismatch(filename, "a SQLite header (GeoPackage)")
        return expected

    if expected is SourceFormat.SHAPEFILE:
        if _be_int(header) != SHAPEFILE_CODE:
            raise _mismatch(filename, "a shapefile header (file code 9994)")
        return expected

    if suffix == ".csv":
        return _detect_csv(filename, header)

    text = _decode(header).lstrip("\ufeff \t\r\n")
    if not text:
        raise IngestError("empty_file", f"{filename} contains no data")
    if text[0] in "{[":
        return SourceFormat.GEOJSON
    raise _mismatch(filename, "JSON text")


def _mismatch(filename: str, expectation: str) -> IngestError:
    return IngestError(
        "format_mismatch",
        f"{filename} does not contain {expectation}; check the file before re-uploading",
        status=415,
    )


def _detect_csv(filename: str, header: bytes) -> SourceFormat:
    text = _decode(header)
    if not text.strip():
        raise IngestError("empty_file", f"{filename} contains no data")
    if text.lstrip()[0] in "{[":
        raise _mismatch(filename, "comma-separated values, not JSON")

    first_line = text.splitlines()[0].lstrip("\ufeff")
    delimiter = "," if "," in first_line else "\t" if "\t" in first_line else None
    headers = (
        [cell.strip() for cell in first_line.split(delimiter)]
        if delimiter
        else [first_line.strip()]
    )
    if not any(headers):
        raise IngestError("empty_file", f"{filename} has an empty header row")
    if find_coordinate_columns(headers) is not None:
        return SourceFormat.CSV_GNSS
    return SourceFormat.CSV_ROR
