"""`POST /sources` against a real PostGIS row and an in-memory object store."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Polygon
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.ingest.store import get_store
from app.main import create_app

BLOCK = Polygon(
    [
        (76.7730, 30.7330),
        (76.7740, 30.7330),
        (76.7740, 30.7340),
        (76.7730, 30.7340),
        (76.7730, 30.7330),
    ]
)


class MemoryStore:
    """Object store double: keeps the bytes so a test can assert they were written."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, stream: Any, length: int, *, content_type: str) -> None:
        assert content_type, "a stored object must declare a content type"
        self.objects[key] = stream.read(length)

    def get(self, key: str) -> bytes:
        try:
            return self.objects[key]
        except KeyError as exc:
            raise FileNotFoundError(key) from exc

    def exists(self, key: str) -> bool:
        return key in self.objects

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@pytest.fixture()
def api(db: Session) -> Iterator[tuple[TestClient, MemoryStore]]:
    store = MemoryStore()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            yield client, store
    finally:
        app.dependency_overrides.clear()


def _geojson(tag: str) -> bytes:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": f"block {tag}"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [76.773, 30.733],
                                [76.774, 30.733],
                                [76.774, 30.734],
                                [76.773, 30.734],
                                [76.773, 30.733],
                            ]
                        ],
                    },
                }
            ],
        }
    ).encode()


def _post(
    client: TestClient,
    *,
    payload: bytes,
    filename: str,
    kind: str = "cadastral",
    name: str,
    extra: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    data: dict[str, str] = {"name": name, "kind": kind, "licence": "ODbL-1.0"}
    data.update(extra or {})
    return client.post(
        "/sources",
        files={"file": (filename, payload, "application/octet-stream")},
        data=data,
        headers=headers or {},
    )


def _test_name() -> str:
    return f"__stage1test__-{uuid4().hex[:12]}"


def test_registers_a_geojson_source(api: tuple[TestClient, MemoryStore]) -> None:
    client, store = api
    name = _test_name()

    response = _post(client, payload=_geojson("one"), filename="layer.geojson", name=name)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == name
    assert body["format"] == "geojson"
    assert body["kind"] == "cadastral"
    assert body["licence"] == "ODbL-1.0"
    assert body["is_synthetic"] is False
    assert body["crs"] == "EPSG:4326"
    assert body["crs_source"] == "file"
    assert body["has_geometry"] is True
    assert body["feature_count"] == 1
    assert len(body["sha256"]) == 64
    assert body["reused"] is False
    assert body["vintage"] is None
    assert body["coverage"] is not None and len(body["coverage"]) == 4
    assert body["object_key"] in store.objects


def test_the_same_bytes_and_kind_register_once(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, _store = api
    name = _test_name()
    payload = _geojson("twice")

    first = _post(client, payload=payload, filename="layer.geojson", name=name)
    second = _post(client, payload=payload, filename="layer.geojson", name=name)

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert second.json()["reused"] is True
    assert second.json()["reuse_reason"] == "same_sha256"
    assert second.json()["source_id"] == first.json()["source_id"]


def test_an_idempotency_key_replays_the_first_row(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, _store = api
    key = f"client-{uuid4().hex}"
    payload = _geojson("replay")

    first = _post(
        client,
        payload=payload,
        filename="layer.geojson",
        name=_test_name(),
        headers={"Idempotency-Key": key},
    )
    second = _post(
        client,
        payload=payload,
        filename="other-name.geojson",
        name=_test_name(),
        headers={"Idempotency-Key": key},
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["reused"] is True
    assert body["reuse_reason"] == "idempotency_key"
    assert body["source_id"] == first.json()["source_id"]


def _shapefile_zip(tmp_path: Path, *, with_prj: bool) -> bytes:
    shp = tmp_path / "parcels.shp"
    gpd.GeoDataFrame({"name": ["block"]}, geometry=[BLOCK], crs="EPSG:4326").to_file(shp)
    if not with_prj:
        shp.with_suffix(".prj").unlink()

    archive = tmp_path / "parcels.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for sidecar in sorted(tmp_path.glob("parcels.*")):
            handle.write(sidecar, arcname=sidecar.name)
    return archive.read_bytes()


def test_refuses_a_shapefile_that_carries_no_crs(
    api: tuple[TestClient, MemoryStore], tmp_path: Path
) -> None:
    client, _store = api

    response = _post(
        client,
        payload=_shapefile_zip(tmp_path, with_prj=False),
        filename="parcels.zip",
        name=_test_name(),
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "missing_crs"
    assert "declared_crs" in response.json()["detail"]["message"]


def test_accepts_the_same_shapefile_when_the_operator_declares_a_crs(
    api: tuple[TestClient, MemoryStore], tmp_path: Path
) -> None:
    client, store = api

    response = _post(
        client,
        payload=_shapefile_zip(tmp_path, with_prj=False),
        filename="parcels.zip",
        name=_test_name(),
        extra={"declared_crs": "EPSG:4326"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["crs"] == "EPSG:4326"
    assert body["crs_source"] == "declared"
    assert body["format"] == "shapefile"
    assert body["crs_declared"] == "EPSG:4326"
    assert any("supplied by the operator" in note for note in body["notes"])
    assert body["object_key"] in store.objects


def test_registers_a_record_table_without_a_crs(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, _store = api

    response = _post(
        client,
        payload=b"khasra,owner,sqm\n12,recorded,505\n",
        filename="ror.csv",
        kind="revenue",
        name=_test_name(),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["crs"] is None
    assert body["has_geometry"] is False
    assert body["format"] == "csv_ror"
    assert body["feature_count"] == 1
    assert body["attributes"] == ["khasra", "owner", "sqm"]


def test_refuses_a_crs_for_a_table_that_has_no_geometry(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, _store = api

    response = _post(
        client,
        payload=b"khasra,owner\n12,recorded\n",
        filename="ror.csv",
        kind="revenue",
        name=_test_name(),
        extra={"declared_crs": "EPSG:32643"},
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "crs_not_applicable"


def test_refuses_a_kind_that_cannot_take_this_format(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, _store = api

    response = _post(
        client,
        payload=b"khasra,owner\n12,recorded\n",
        filename="ror.csv",
        kind="dsm",
        name=_test_name(),
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "format_not_allowed_for_kind"


def test_refuses_an_unknown_kind(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api

    response = _post(
        client,
        payload=_geojson("kind"),
        filename="layer.geojson",
        kind="mystery",
        name=_test_name(),
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["code"] == "unknown_kind"
    assert "cadastral" in response.json()["detail"]["message"]


def test_refuses_an_upload_with_no_licence(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api

    response = client.post(
        "/sources",
        files={"file": ("layer.geojson", _geojson("nolicence"), "application/octet-stream")},
        data={"name": _test_name(), "kind": "cadastral"},
    )

    assert response.status_code == 422
    errors = [error["loc"] for error in response.json()["detail"]]
    assert ["body", "licence"] in errors


def test_lists_and_reads_sources_back(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    name = _test_name()

    created = _post(client, payload=_geojson("readback"), filename="layer.geojson", name=name)
    assert created.status_code == 201, created.text
    source_id = created.json()["source_id"]

    listing = client.get("/sources", params={"limit": 100})
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == len(body["items"])
    assert any(item["source_id"] == source_id for item in body["items"])

    detail = client.get(f"/sources/{source_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == name

    missing = client.get("/sources/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "source_not_found"


def test_list_filters_by_kind(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api

    _post(client, payload=_geojson("k1"), filename="layer.geojson", name=_test_name())
    _post(
        client,
        payload=b"khasra,owner\n12,recorded\n",
        filename="ror.csv",
        kind="revenue",
        name=_test_name(),
    )

    revenue = client.get("/sources", params={"kind": "revenue", "limit": 100})
    assert revenue.status_code == 200
    assert {item["kind"] for item in revenue.json()["items"]} == {"revenue"}


def test_serves_loaded_features_as_wgs84_geojson(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    created = _post(
        client, payload=_geojson("mapview"), filename="layer.geojson", name=_test_name()
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["source_id"]

    response = client.get(f"/sources/{source_id}/features.geojson")

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/geo+json")
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["total"] == 1
    assert "truncated" not in body
    feature = body["features"][0]
    assert feature["properties"]["feature_class"] == "parcel"
    assert feature["properties"]["props"]["name"] == "block mapview"
    lon, lat = feature["geometry"]["coordinates"][0][0]
    assert 76.7 < lon < 76.9 and 30.6 < lat < 30.8, "geometry must be reprojected to WGS 84"


def test_features_of_a_geometry_less_source_is_an_empty_collection(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, _store = api
    created = _post(
        client,
        payload=b"khasra,owner,sqm\n12,recorded,505\n",
        filename="ror.csv",
        kind="revenue",
        name=_test_name(),
    )
    assert created.status_code == 201, created.text

    response = client.get(f"/sources/{created.json()['source_id']}/features.geojson")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["features"] == []
    assert body["total"] == 0


def test_features_endpoint_refuses_an_unknown_source(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, _store = api

    response = client.get("/sources/00000000-0000-0000-0000-000000000000/features.geojson")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "source_not_found"


def _geotiff() -> bytes:
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    with rasterio.MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff",
            width=16,
            height=16,
            count=3,
            dtype="uint8",
            crs="EPSG:32643",
            transform=from_origin(700_000, 3_350_000, 10, 10),
        ) as dst:
            dst.write(np.full((3, 16, 16), 120, dtype="uint8"))
        return memfile.read()


def test_raster_preview_reports_bounds_and_png(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    created = _post(
        client,
        payload=_geotiff(),
        filename="flight.tif",
        kind="drone_ori",
        name=_test_name(),
        extra={"is_synthetic": "true"},
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["source_id"]

    info = client.get(f"/sources/{source_id}/preview")
    assert info.status_code == 200, info.text
    body = info.json()
    west, south, east, north = body["bounds"]
    assert west < east and south < north
    assert 70 < west < 80 and 25 < south < 35, "bounds must be plausible WGS 84"
    assert body["png"] == f"/sources/{source_id}/preview.png"
    assert body["width"] == 16 and body["height"] == 16

    image = client.get(f"/sources/{source_id}/preview.png")
    assert image.status_code == 200, image.text
    assert image.headers["content-type"] == "image/png"
    assert image.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_preview_is_refused_for_vector_sources(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    created = _post(client, payload=_geojson("norgb"), filename="layer.geojson", name=_test_name())
    assert created.status_code == 201, created.text

    info = client.get(f"/sources/{created.json()['source_id']}/preview")
    assert info.status_code == 404
    assert info.json()["detail"]["code"] == "no_preview"


def test_preview_refuses_an_unknown_source(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api

    info = client.get("/sources/00000000-0000-0000-0000-000000000000/preview")

    assert info.status_code == 404
    assert info.json()["detail"]["code"] == "source_not_found"


def test_reuse_restores_bytes_the_store_lost(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, store = api
    name = _test_name()
    payload = _geojson("wipe")

    first = _post(client, payload=payload, filename="layer.geojson", name=name)
    assert first.status_code == 201, first.text
    key = first.json()["object_key"]
    store.objects.pop(key)  # the ephemeral bucket was emptied by a redeploy

    second = _post(client, payload=payload, filename="layer.geojson", name=name)

    assert second.status_code == 200, second.text
    assert second.json()["reused"] is True
    assert key in store.objects, "reuse must repopulate bytes the store lost"
    assert store.objects[key] == payload


def test_delete_removes_row_features_and_bytes(api: tuple[TestClient, MemoryStore]) -> None:
    client, store = api
    created = _post(client, payload=_geojson("gone"), filename="layer.geojson", name=_test_name())
    assert created.status_code == 201, created.text
    source_id = created.json()["source_id"]
    key = created.json()["object_key"]

    listed = client.get(f"/sources/{source_id}/features.geojson")
    assert listed.status_code == 200, listed.text

    removed = client.delete(f"/sources/{source_id}")
    assert removed.status_code == 204
    assert client.get(f"/sources/{source_id}").status_code == 404
    assert client.get(f"/sources/{source_id}/features.geojson").status_code == 404
    assert key not in store.objects, "the stored bytes must go with the row"
    assert client.delete(f"/sources/{source_id}").status_code == 404
