"""Format detection: what the bytes say beats what the filename says."""

from pathlib import Path

import pytest

from app.domain.sources import SourceFormat
from app.ingest.detect import detect_format, is_archive, read_header
from app.ingest.errors import IngestError

GEOJSON = b'{"type": "FeatureCollection", "features": []}'
CSV_GNSS = b"latitude,longitude\n30.73,76.77\n"
CSV_ROR = b"khasra,owner,sqm\n12,recorded,505\n"


def _write(tmp_path: Path, name: str, payload: bytes) -> tuple[str, bytes]:
    path = tmp_path / name
    path.write_bytes(payload)
    return name, read_header(path)


def test_detects_geojson_by_content(tmp_path: Path) -> None:
    name, header = _write(tmp_path, "layer.json", GEOJSON)
    assert detect_format(name, header) is SourceFormat.GEOJSON


def test_detects_geotiff_by_magic(tmp_path: Path) -> None:
    name, header = _write(tmp_path, "ori.tif", b"II*\x00" + b"\x00" * 64)
    assert detect_format(name, header) is SourceFormat.GEOTIFF


def test_detects_geopackage_by_magic(tmp_path: Path) -> None:
    name, header = _write(tmp_path, "layers.gpkg", b"SQLite format 3\x00" + b"\x00" * 64)
    assert detect_format(name, header) is SourceFormat.GPKG


def test_detects_shapefile_by_file_code(tmp_path: Path) -> None:
    code = (9994).to_bytes(4, "big")
    name, header = _write(tmp_path, "parcels.shp", code + b"\x00" * 64)
    assert detect_format(name, header) is SourceFormat.SHAPEFILE


def test_csv_with_a_coordinate_pair_is_a_gnss_export(tmp_path: Path) -> None:
    name, header = _write(tmp_path, "points.csv", CSV_GNSS)
    assert detect_format(name, header) is SourceFormat.CSV_GNSS


def test_csv_without_a_coordinate_pair_is_a_record_table(tmp_path: Path) -> None:
    name, header = _write(tmp_path, "ror.csv", CSV_ROR)
    assert detect_format(name, header) is SourceFormat.CSV_ROR


def test_refuses_a_file_whose_bytes_contradict_the_extension(tmp_path: Path) -> None:
    name, header = _write(tmp_path, "ori.tif", GEOJSON)
    with pytest.raises(IngestError) as excinfo:
        detect_format(name, header)
    assert excinfo.value.code == "format_mismatch"
    assert excinfo.value.status == 415


def test_refuses_an_unknown_extension(tmp_path: Path) -> None:
    name, header = _write(tmp_path, "notes.txt", b"hello")
    with pytest.raises(IngestError) as excinfo:
        detect_format(name, header)
    assert excinfo.value.code == "unsupported_extension"


def test_refuses_to_detect_a_zip(tmp_path: Path) -> None:
    name, header = _write(tmp_path, "bundle.zip", b"PK\x03\x04" + b"\x00" * 32)
    with pytest.raises(IngestError) as excinfo:
        detect_format(name, header)
    assert excinfo.value.code == "unexpected_archive"


def test_refuses_an_empty_file(tmp_path: Path) -> None:
    name, header = _write(tmp_path, "empty.geojson", b"")
    with pytest.raises(IngestError) as excinfo:
        detect_format(name, header)
    assert excinfo.value.code == "empty_file"


def test_recognises_an_archive_by_name_and_by_bytes(tmp_path: Path) -> None:
    csv_path = tmp_path / "a.csv"
    csv_path.write_bytes(CSV_GNSS)
    assert is_archive("bundle.zip", read_header(csv_path))

    by_bytes = tmp_path / "odd.bin"
    by_bytes.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    assert is_archive("odd.bin", read_header(by_bytes))

    layer = tmp_path / "layer.geojson"
    layer.write_bytes(GEOJSON)
    assert not is_archive("layer.geojson", read_header(layer))
