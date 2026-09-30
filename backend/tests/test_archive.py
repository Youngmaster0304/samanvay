"""Archive unpacking: nothing escapes the destination, and one bundle means one layer."""

import zipfile
from pathlib import Path

import pytest

from app.ingest.archive import unpack_archive
from app.ingest.errors import IngestError

GEOJSON = b'{"type": "FeatureCollection", "features": []}'


def _zip(tmp_path: Path, name: str, entries: dict[str, bytes]) -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as handle:
        for member, data in entries.items():
            handle.writestr(member, data)
    return path


def test_unpacks_a_single_geojson(tmp_path: Path) -> None:
    archive = _zip(tmp_path, "bundle.zip", {"layer.geojson": GEOJSON})
    result = unpack_archive(archive, tmp_path / "out", max_entries=10, max_bytes=1 << 20)
    assert result.payload.name == "layer.geojson"
    assert result.payload.read_bytes() == GEOJSON
    assert result.members == ["layer.geojson"]


def test_selects_the_shapefile_and_keeps_its_sidecars(tmp_path: Path) -> None:
    archive = _zip(
        tmp_path,
        "parcels.zip",
        {
            "parcels.shp": (9994).to_bytes(4, "big") + b"\x00" * 64,
            "parcels.dbf": b"data",
            "parcels.shx": b"index",
            "parcels.prj": b"PROJCS",
        },
    )
    result = unpack_archive(archive, tmp_path / "out", max_entries=10, max_bytes=1 << 20)
    assert result.payload.name == "parcels.shp"
    assert sorted(result.members) == [
        "parcels.dbf",
        "parcels.prj",
        "parcels.shp",
        "parcels.shx",
    ]


def test_refuses_a_member_that_escapes_the_destination(tmp_path: Path) -> None:
    archive = _zip(tmp_path, "evil.zip", {"../escaped.geojson": GEOJSON})
    with pytest.raises(IngestError) as excinfo:
        unpack_archive(archive, tmp_path / "out", max_entries=10, max_bytes=1 << 20)
    assert excinfo.value.code == "archive_unsafe_path"


def test_refuses_an_absolute_member_path(tmp_path: Path) -> None:
    archive = _zip(tmp_path, "evil2.zip", {"/etc/passwd": b"root"})
    with pytest.raises(IngestError) as excinfo:
        unpack_archive(archive, tmp_path / "out", max_entries=10, max_bytes=1 << 20)
    assert excinfo.value.code == "archive_unsafe_path"


def test_refuses_a_bundle_with_two_candidate_layers(tmp_path: Path) -> None:
    archive = _zip(
        tmp_path,
        "two.zip",
        {"a.geojson": GEOJSON, "b.geojson": GEOJSON},
    )
    with pytest.raises(IngestError) as excinfo:
        unpack_archive(archive, tmp_path / "out", max_entries=10, max_bytes=1 << 20)
    assert excinfo.value.code == "ambiguous_archive"
    assert "a.geojson" in excinfo.value.message
    assert "b.geojson" in excinfo.value.message


def test_refuses_a_bundle_with_no_payload(tmp_path: Path) -> None:
    archive = _zip(tmp_path, "notes.zip", {"readme.txt": b"hello"})
    with pytest.raises(IngestError) as excinfo:
        unpack_archive(archive, tmp_path / "out", max_entries=10, max_bytes=1 << 20)
    assert excinfo.value.code == "archive_without_payload"


def test_refuses_more_entries_than_the_limit(tmp_path: Path) -> None:
    archive = _zip(tmp_path, "many.zip", {"layer.geojson": GEOJSON, "a.txt": b"x"})
    with pytest.raises(IngestError) as excinfo:
        unpack_archive(archive, tmp_path / "out", max_entries=1, max_bytes=1 << 20)
    assert excinfo.value.code == "archive_too_many_entries"
    assert excinfo.value.status == 413


def test_refuses_a_bundle_that_unpacks_too_large(tmp_path: Path) -> None:
    archive = _zip(tmp_path, "big.zip", {"layer.geojson": GEOJSON})
    with pytest.raises(IngestError) as excinfo:
        unpack_archive(archive, tmp_path / "out", max_entries=10, max_bytes=1)
    assert excinfo.value.code == "archive_too_large"
    assert excinfo.value.status == 413


def test_refuses_a_file_that_is_not_actually_a_zip(tmp_path: Path) -> None:
    not_a_zip = tmp_path / "bundle.zip"
    not_a_zip.write_bytes(GEOJSON)
    with pytest.raises(IngestError) as excinfo:
        unpack_archive(not_a_zip, tmp_path / "out", max_entries=10, max_bytes=1 << 20)
    assert excinfo.value.code == "not_an_archive"
    assert excinfo.value.status == 415
