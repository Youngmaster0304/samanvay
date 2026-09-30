"""Safe unpacking of an uploaded zip, and selection of the one payload inside it.

Two rules, both refusals rather than repairs: nothing outside the destination directory
may be written, and a bundle holding more than one candidate layer is not guessed at.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.ingest.errors import IngestError

# What a bundle is allowed to contain as its payload. Sidecars (.dbf, .shx, .prj, .cpg)
# are deliberately absent: they travel with their shapefile, they are never a payload.
PAYLOAD_SUFFIXES = (".shp", ".geojson", ".gpkg", ".tif", ".tiff", ".csv")

_RATIO_LIMIT = 1000  # uncompressed / compressed, for a single entry over 10 MiB
_RATIO_FLOOR = 10 * 1024 * 1024


@dataclass(frozen=True)
class Unpacked:
    """Where the archive was unpacked, and which file inside it is the payload."""

    root: Path
    payload: Path
    members: list[str]


def _safe_member(name: str) -> str:
    """Return the member path relative to the extraction root, or refuse it."""
    normalised = name.replace("\\", "/")
    path = PurePosixPath(normalised)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise IngestError(
            "archive_unsafe_path",
            f"the archive contains an entry that would be written outside the unpack "
            f"directory ({name!r}); repack it and upload again",
            status=422,
        )
    if path.parts and (len(path.parts[0]) == 2 and path.parts[0][1] == ":"):
        raise IngestError(
            "archive_unsafe_path",
            f"the archive contains an absolute path ({name!r}); repack it and upload again",
        )
    stripped = [part for part in path.parts if part not in ("", ".")]
    if not stripped:
        raise IngestError(
            "archive_unsafe_path",
            f"the archive contains an entry with no usable name ({name!r})",
        )
    return "/".join(stripped)


def unpack_archive(
    archive: Path,
    dest: Path,
    *,
    max_entries: int,
    max_bytes: int,
) -> Unpacked:
    """Unpack `archive` into `dest` and return the single payload it holds."""
    if not zipfile.is_zipfile(archive):
        raise IngestError(
            "not_an_archive",
            "the uploaded file is not a zip archive even though its name suggests one",
            status=415,
        )

    with zipfile.ZipFile(archive) as handle:
        infos = handle.infolist()
        if len(infos) > max_entries:
            raise IngestError(
                "archive_too_many_entries",
                f"the archive holds {len(infos)} entries, more than the "
                f"{max_entries} allowed for one upload",
                status=413,
            )

        total = sum(info.file_size for info in infos)
        if total > max_bytes:
            raise IngestError(
                "archive_too_large",
                f"the archive unpacks to {total} bytes, more than the {max_bytes} "
                "allowed for one upload",
                status=413,
            )

        members: list[str] = []
        for info in infos:
            if info.is_dir():
                continue
            if (
                info.file_size > _RATIO_FLOOR
                and info.file_size / max(info.compress_size, 1) > _RATIO_LIMIT
            ):
                raise IngestError(
                    "archive_suspicious_ratio",
                    f"{info.filename!r} unpacks to {info.file_size} bytes from "
                    f"{info.compress_size}; refusing a member with a "
                    f"{_RATIO_LIMIT}:1 compression ratio",
                    status=413,
                )
            target = _safe_member(info.filename)
            out_path = dest / target
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with handle.open(info) as source, open(out_path, "wb") as sink:
                while chunk := source.read(1 << 20):
                    sink.write(chunk)
            members.append(target)

    return Unpacked(root=dest, payload=_select_payload(dest, members), members=members)


def _select_payload(root: Path, members: list[str]) -> Path:
    """Exactly one file in the bundle may be the payload; anything else is refused."""
    candidates = [
        root / member for member in members if Path(member).suffix.lower() in PAYLOAD_SUFFIXES
    ]
    if not candidates:
        raise IngestError(
            "archive_without_payload",
            "the archive holds no supported file (" + ", ".join(PAYLOAD_SUFFIXES) + ")",
            status=415,
        )

    shapefiles = [path for path in candidates if path.suffix.lower() == ".shp"]
    others = [path for path in candidates if path.suffix.lower() != ".shp"]

    if len(shapefiles) == 1 and not others:
        return shapefiles[0]

    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise IngestError(
            "ambiguous_archive",
            f"the archive holds more than one candidate layer ({names}); "
            "upload one layer per archive so no file has to be chosen for you",
            status=422,
        )

    return candidates[0]
