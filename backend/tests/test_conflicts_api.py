"""Conflict endpoints against real PostGIS rows (plan Stage 6 first slice).

Covers: polygon overlap detection with policy severities, boundary-crossing detection
with measured length outside, the reviewer decision flow with append-only history,
idempotent re-detection, and every refusal this slice can hit.
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


def _line(points: list[tuple[float, float]]) -> dict[str, object]:
    return {"type": "LineString", "coordinates": [list(point) for point in points]}


def _register(client: TestClient, geometry: dict[str, object], kind: str = "cadastral") -> str:
    payload = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": geometry}],
        }
    ).encode()
    name = _test_name()
    response = _post(client, payload=payload, filename=f"{name}.geojson", kind=kind, name=name)
    assert response.status_code == 201, response.text
    source_id = response.json()["source_id"]
    loaded = client.post(f"/sources/{source_id}/load")
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["loaded"] == 1, loaded.text
    return source_id


def _pair(client: TestClient, source_a: str, source_b: str, state: str = "queue") -> list[dict]:
    """Queue rows for exactly this source pair.

    The tests share the live database, so pilot rows and other runs are in the
    same table; every assertion must count only what this test detected.
    """
    response = client.get("/conflicts", params={"state": state})
    assert response.status_code == 200, response.text
    return [
        item
        for item in response.json()["items"]
        if item["source_a"] == source_a and item["source_b"] == source_b
    ]


def test_overlap_is_queued_with_policy_severity_then_decided(
    db: Session, api: tuple[TestClient, MemoryStore]
) -> None:
    client, _store = api
    # Two ~0.001° squares overlapping in a ~10 000 m² block: above the high threshold.
    source_a = _register(client, _square(76.773, 30.733, 76.775, 30.735))
    source_b = _register(client, _square(76.774, 30.734, 76.776, 30.736), kind="footprint_ai")

    detected = client.post("/conflicts/detect", json={"source_a": source_a, "source_b": source_b})
    assert detected.status_code == 201, detected.text
    summary = detected.json()
    assert summary["pairs_examined"] == 1
    assert summary["created"] == 1
    assert summary["by_type"] == {"overlap": 1}
    assert summary["by_severity"] == {"high": 1}
    limits = summary["policy"]["limits"]
    assert limits["overlap_high_m2"] == 100.0 and limits["max_pairs"] == 5000.0

    items = _pair(client, source_a, source_b)
    assert len(items) == 1
    item = items[0]
    assert item["type"] == "overlap" and item["severity"] == "high"
    assert item["area_m2"] is not None and item["area_m2"] >= 100.0
    assert item["geometry"] is not None and item["geometry"]["type"] == "Polygon"
    assert "m²" in item["reason"] and "naksha" in item["reason"]

    decided = client.post(
        f"/conflicts/{item['conflict_id']}/decision",
        json={"action": "accept_a", "reason_code": "authoritative_source", "actor": "reviewer1"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["state"] == "resolved"
    assert decided.json()["decision"]["action"] == "accept_a"

    repeat = client.post(
        f"/conflicts/{item['conflict_id']}/decision",
        json={"action": "reject", "reason_code": "changed_my_mind"},
    )
    assert repeat.status_code == 409, repeat.text
    assert repeat.json()["detail"]["code"] == "already_decided"

    assert _pair(client, source_a, source_b) == []
    assert len(_pair(client, source_a, source_b, state="resolved")) == 1

    # Re-detection never clobbers history: the decided pair stays decided.
    again = client.post("/conflicts/detect", json={"source_a": source_a, "source_b": source_b})
    assert again.status_code == 201, again.text
    assert again.json()["created"] == 0
    assert _pair(client, source_a, source_b) == []


def test_line_leaving_a_polygon_is_queued_with_measured_length(
    api: tuple[TestClient, MemoryStore],
) -> None:
    client, _store = api
    boundary = _register(client, _square(76.773, 30.733, 76.775, 30.735))
    # Exits the east edge at 76.7750 and runs ~0.0001° (~10 m) beyond: medium crossing.
    road = _register(client, _line([(76.7735, 30.7335), (76.7751, 30.7335)]), kind="municipal")

    detected = client.post("/conflicts/detect", json={"source_a": road, "source_b": boundary})
    assert detected.status_code == 201, detected.text
    assert detected.json()["by_type"] == {"boundary_crossing": 1}

    items = _pair(client, road, boundary)
    assert len(items) == 1
    item = items[0]
    assert item["type"] == "boundary_crossing"
    assert item["severity"] == "medium"
    assert item["outside_m"] is not None and 5.0 <= item["outside_m"] < 50.0
    assert item["area_m2"] is None
    assert "outside" in item["reason"]


def test_refusals_are_specific(api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    source_a = _register(client, _square(76.773, 30.733, 76.774, 30.734))

    same = client.post("/conflicts/detect", json={"source_a": source_a, "source_b": source_a})
    assert same.status_code == 422 and same.json()["detail"]["code"] == "same_source"

    missing = str(uuid4())
    unknown = client.post("/conflicts/detect", json={"source_a": source_a, "source_b": missing})
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
        "/conflicts/detect",
        json={"source_a": source_a, "source_b": csv.json()["source_id"]},
    )
    assert not_loaded.status_code == 422
    assert not_loaded.json()["detail"]["code"] == "source_not_loaded"

    missing_decision = client.post(
        f"/conflicts/{uuid4()}/decision",
        json={"action": "defer", "reason_code": "needs_survey"},
    )
    assert missing_decision.status_code == 404
    assert missing_decision.json()["detail"]["code"] == "conflict_not_found"
