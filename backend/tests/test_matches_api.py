"""Matching endpoints against real PostGIS rows (plan Stage 4 first slice).

Covers: IoU scoring with the policy accept threshold, greedy one-to-one
assignment (one feature never matches twice), idempotent re-detection, and
this slice's refusals.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_georef_api import MemoryStore, _post, _test_name

from app.db.session import get_session
from app.ingest.store import get_store
from app.main import create_app


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


def _square(west: float, south: float, east: float, north: float) -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [
            [[west, south], [east, south], [east, north], [west, north], [west, south]]
        ],
    }


def _register_many(
    client: TestClient, geometries: list[dict[str, object]], kind: str = "cadastral"
) -> str:
    payload = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {}, "geometry": geometry}
                for geometry in geometries
            ],
        }
    ).encode()
    name = _test_name()
    response = _post(client, payload=payload, filename=f"{name}.geojson", kind=kind, name=name)
    assert response.status_code == 201, response.text
    source_id = response.json()["source_id"]
    loaded = client.post(f"/sources/{source_id}/load")
    assert loaded.status_code == 200, loaded.text
    return source_id


def _pairs_for(client: TestClient, source_a: str, source_b: str) -> list[dict]:
    """Matches for exactly this source pair (the tests share the live database)."""
    response = client.get("/matches", params={"source": source_a})
    assert response.status_code == 200, response.text
    return [
        item
        for item in response.json()["items"]
        if {item["source_a"], item["source_b"]} == {source_a, source_b}
    ]


def test_greedy_assignment_is_one_to_one_and_above_the_threshold(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, _store = api
    # Source A: one square. Source B: the same square shifted east and west by
    # ~0.0004 deg (~38 m): each pair intersects at IoU ~0.67, above the 0.60
    # accept threshold, but A has only one feature — greedy keeps the better one.
    source_a = _register_many(client, [_square(76.773, 30.733, 76.775, 30.735)])
    source_b = _register_many(
        client,
        [
            _square(76.7734, 30.733, 76.7754, 30.735),
            _square(76.7726, 30.733, 76.7746, 30.735),
        ],
        kind="footprint_ai",
    )

    detected = client.post("/matches/detect", json={"source_a": source_a, "source_b": source_b})
    assert detected.status_code == 201, detected.text
    summary = detected.json()
    assert summary["pairs_examined"] == 2
    assert summary["polygon_candidates"] == 2
    assert summary["assigned"] == 1
    assert summary["assignment"] == "hungarian"
    assert summary["greedy_fallback_components"] == 0
    assert summary["blocking_radius_m"] >= 15.0
    assert summary["score_min"] is not None and summary["score_min"] >= 0.60
    assert summary["score_max"] is not None and summary["score_max"] <= 1.0
    limits = summary["policy"]["limits"]
    assert limits["accept_threshold"] == 0.60 and limits["max_pairs"] == 5000.0
    assert summary["policy"]["weights"]["iou"] == 3.0

    items = _pairs_for(client, source_a, source_b)
    assert len(items) == 1
    assert items[0]["score"] >= 0.60
    assert items[0]["method"] == "hungarian"
    stored = items[0]["pair_features"]
    assert stored is not None and stored["iou"] > 0.5 and stored["distance_m"] > 0
    assert "naksha" in items[0]["source_a_name"] or items[0]["source_a_name"]

    # Re-running replaces the pair whole: still exactly one row, no duplicates.
    again = client.post("/matches/detect", json={"source_a": source_a, "source_b": source_b})
    assert again.status_code == 201, again.text
    assert again.json()["assigned"] == 1
    assert len(_pairs_for(client, source_a, source_b)) == 1


def test_disjoint_and_refusals(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    source_a = _register_many(client, [_square(76.773, 30.733, 76.774, 30.734)])
    far_b = _register_many(client, [_square(76.780, 30.740, 76.781, 30.741)], kind="municipal")

    # Disjoint sources: nothing to candidates, nothing assigned.
    disjoint = client.post("/matches/detect", json={"source_a": source_a, "source_b": far_b})
    assert disjoint.status_code == 201, disjoint.text
    assert disjoint.json()["pairs_examined"] == 0
    assert disjoint.json()["assigned"] == 0
    assert _pairs_for(client, source_a, far_b) == []

    same = client.post("/matches/detect", json={"source_a": source_a, "source_b": source_a})
    assert same.status_code == 422 and same.json()["detail"]["code"] == "same_source"

    missing = str(uuid4())
    unknown = client.post("/matches/detect", json={"source_a": source_a, "source_b": missing})
    assert unknown.status_code == 404 and unknown.json()["detail"]["code"] == "source_not_found"

    csv = _post(
        client,
        payload=b"khasra,owner,sqm\n12,recorded,505\n",
        filename="ror.csv",
        kind="revenue",
        name=_test_name(),
    )
    assert csv.status_code == 201, csv.text
    not_loaded = client.post(
        "/matches/detect",
        json={"source_a": source_a, "source_b": csv.json()["source_id"]},
    )
    assert not_loaded.status_code == 422
    assert not_loaded.json()["detail"]["code"] == "source_not_loaded"
