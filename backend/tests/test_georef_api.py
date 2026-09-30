"""Georeferencing endpoints against a real PostGIS row and an in-memory object store.

Covers plan Stage 2: fit control points -> read the fit back -> load features into the
storage CRS -> read health, plus the refusals (too few points, unknown source) and the
honest skip when a source has no geometry to load.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pyproj import Transformer
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_sources_api import MemoryStore, _geojson, _post, _test_name

from app.db.models import SourceFeature
from app.db.session import get_session
from app.ingest.store import get_store
from app.main import create_app

_TO_STORAGE = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


@pytest.fixture()
def api(db: Session) -> Iterator[tuple[TestClient, MemoryStore]]:
    """The app wired to the test database and to bytes kept in memory."""
    store = MemoryStore()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db
    app.dependency_overrides[get_store] = lambda: store
    try:
        with TestClient(app) as client:
            yield client, store
    finally:
        app.dependency_overrides.clear()


def _control_pairs() -> list[dict[str, object]]:
    """Five surveyed corners: the source sits 0.5 m east, 0.3 m south of the truth."""
    corners = [
        (76.7730, 30.7330),
        (76.7740, 30.7330),
        (76.7740, 30.7340),
        (76.7730, 30.7340),
        (76.7735, 30.7335),
    ]
    pairs: list[dict[str, object]] = []
    for index, (lon, lat) in enumerate(corners):
        x, y = _TO_STORAGE.transform(lon, lat)
        pairs.append({"from": [x, y], "to": [x + 0.5, y - 0.3], "label": f"corner{index}"})
    return pairs


def _register_vector(client: TestClient) -> str:
    response = _post(
        client, payload=_geojson("georef"), filename="layer.geojson", name=_test_name()
    )
    assert response.status_code == 201, response.text
    return response.json()["source_id"]


def test_fit_load_and_health_flow(db: Session, api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    source_id = _register_vector(client)

    fit = client.post(f"/sources/{source_id}/georef", json={"pairs": _control_pairs(), "unit": "m"})
    assert fit.status_code == 201, fit.text
    report = fit.json()
    assert report["model"] == "affine"
    assert report["n_control"] == 5
    assert report["unit"] == "m"
    assert report["transform_log_id"]
    assert report["policy"] == {
        "min_control_points": 4,
        "blunder_sigma": 3.5,
        "blunder_floor_m": 0.5,
    }
    assert report["rmse"] < 1e-6
    assert report["blunders"] == []
    assert report["blunder_threshold"] >= 0.5
    scores = {entry["model"]: entry["loo_rmse"] for entry in report["models"]}
    assert set(scores) == {"affine", "poly2", "tps"}
    assert scores["affine"] is not None and scores["affine"] < 1e-6
    assert scores["poly2"] is None, "five points cannot support a second-order polynomial"
    assert len(report["residuals"]) == 5

    read_back = client.get(f"/sources/{source_id}/georef")
    assert read_back.status_code == 200, read_back.text
    assert read_back.json()["transform_log_id"] == report["transform_log_id"]
    assert read_back.json()["pipeline"] == "affine"

    loaded = client.post(f"/sources/{source_id}/load")
    assert loaded.status_code == 200, loaded.text
    summary = loaded.json()
    assert summary["loaded"] == 1
    assert summary["by_class"] == {"parcel": 1}
    assert summary["storage_srid"] == 32643
    assert summary["georef_applied"] is True
    assert summary["georef_transform_log_id"] == report["transform_log_id"]
    assert summary["pipeline"].startswith("+proj=pipeline")
    assert "zone=43" in summary["pipeline"], "the pipeline must be the UTM 43N operation"

    again = client.post(f"/sources/{source_id}/load")
    assert again.status_code == 200, again.text
    assert again.json()["loaded"] == 1

    count = db.execute(
        select(func.count())
        .select_from(SourceFeature)
        .where(SourceFeature.source_id == UUID(source_id))
    ).scalar_one()
    assert count == 1, "a reload upserts instead of duplicating observations"

    health = client.get(f"/sources/{source_id}/health")
    assert health.status_code == 200, health.text
    body = health.json()
    assert body["storage_srid"] == 32643
    assert body["declared_crs"] == "EPSG:4326"
    assert body["crs_source"] == "file"
    assert body["loaded"]["features"] == 1
    assert body["loaded"]["by_class"] == {"parcel": 1}
    assert body["georef"] is not None and body["georef"]["model"] == "affine"
    assert body["transform"] is not None and body["transform"]["pipeline"]


def test_ingesting_a_vector_source_loads_it_with_a_note(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, _store = api
    source_id = _register_vector(client)

    source = client.get(f"/sources/{source_id}")
    assert source.status_code == 200, source.text
    notes = source.json()["notes"]
    assert any(
        note.startswith("loaded 1 features into storage CRS EPSG:32643") for note in notes
    ), notes


def test_fit_refuses_too_few_control_points(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    source_id = _register_vector(client)

    response = client.post(f"/sources/{source_id}/georef", json={"pairs": _control_pairs()[:3]})

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "insufficient_control_points"
    assert "4" in detail["message"]


def test_reading_a_fit_before_any_exists_is_404(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    source_id = _register_vector(client)

    response = client.get(f"/sources/{source_id}/georef")

    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "no_georef"


def test_every_endpoint_refuses_an_unknown_source(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    missing = "4fa9c1d0-0000-4000-8000-000000000000"

    for method, path in (
        ("get", f"/sources/{missing}/georef"),
        ("post", f"/sources/{missing}/load"),
        ("get", f"/sources/{missing}/health"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "source_not_found"


def test_loading_a_table_without_geometry_says_so(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    registered = _post(
        client,
        payload=b"khasra,owner,sqm\n12,recorded,505\n",
        filename="ror.csv",
        kind="revenue",
        name=_test_name(),
    )
    assert registered.status_code == 201, registered.text
    source_id = registered.json()["source_id"]

    loaded = client.post(f"/sources/{source_id}/load")
    assert loaded.status_code == 200, loaded.text
    summary = loaded.json()
    assert summary["loaded"] == 0
    assert summary["skipped"] in {"no_geometry", "no_crs"}
    assert summary["reason"]

    notes = client.get(f"/sources/{source_id}").json()["notes"]
    assert any(note.startswith("feature load skipped") for note in notes), notes
