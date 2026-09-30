"""Geometry QC: unit checks on the flag vocabulary plus the load → health contract.

Covers plan Stage 3 (polygon QC): every flag must be derivable from the stored
geometry alone, thresholds must come from the policy, and a reload must keep the
flags (the upsert carries `qc_flags`).
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString, Polygon
from sqlalchemy.orm import Session
from test_georef_api import MemoryStore, _post, _test_name

from app.core.policy import PolicyBundle
from app.db.models import SourceFeature
from app.db.session import get_session
from app.ingest.errors import IngestError
from app.ingest.store import get_store
from app.main import create_app
from app.qc import qc_flags_for, qc_limits

LIMITS = {"min_polygon_area_m2": 1.0}

# Degree geometries for the ingest round-trip test below (they are read back in UTM).
VALID = Polygon([(76.7730, 30.7330), (76.7736, 30.7330), (76.7736, 30.7336), (76.7730, 30.7336)])
BOWTIE = Polygon([(76.7740, 30.7340), (76.7746, 30.7346), (76.7746, 30.7340), (76.7740, 30.7346)])
# ~9.6 m x ~0.05 m: a valid but far-too-thin outline (0.5 m² < 1 m² policy cut-off).
SLIVER = Polygon(
    [
        (76.7750, 30.7340),
        (76.7751, 30.7340),
        (76.7751, 30.73400045),
        (76.7750, 30.73400045),
    ]
)
DUP_VERTEX = Polygon(
    [
        (76.7760, 30.7350),
        (76.7766, 30.7350),
        (76.7766, 30.7350),
        (76.7766, 30.7356),
        (76.7760, 30.7356),
    ]
)


def test_flag_vocabulary_comes_from_the_geometry_alone() -> None:
    # The unit checks run where the load applies them: storage-CRS metres.
    valid = Polygon([(0, 0), (60, 0), (60, 60), (0, 60)])
    bowtie = Polygon([(0, 100), (60, 160), (60, 100), (0, 160)])
    sliver = Polygon([(200, 0), (209.6, 0), (209.6, 0.05), (200, 0.05)])
    dup = Polygon([(300, 0), (360, 0), (360, 0), (360, 60), (300, 60)])
    assert qc_flags_for(valid, limits=LIMITS) == []
    # The bowtie's shoelace area cancels to zero, so it honestly carries two flags.
    assert qc_flags_for(bowtie, limits=LIMITS) == ["invalid_geometry", "sliver_area"]
    assert qc_flags_for(sliver, limits=LIMITS) == ["sliver_area"]
    assert qc_flags_for(dup, limits=LIMITS) == ["duplicate_vertex"]
    # Lines never receive polygon checks.
    assert qc_flags_for(LineString([(0, 0), (1, 1), (2, 0)]), limits=LIMITS) == []


def test_thresholds_must_exist_in_the_policy() -> None:
    good = PolicyBundle(path="p", name="n", version="1", data={"qc": {"min_polygon_area_m2": 1}})
    assert qc_limits(good) == {"min_polygon_area_m2": 1.0}
    for bad in ({}, {"qc": {"min_polygon_area_m2": -1}}, {"qc": {"min_polygon_area_m2": "1"}}):
        bundle = PolicyBundle(path="p", name="n", version="1", data=bad)
        with pytest.raises(IngestError) as excinfo:
            qc_limits(bundle)
        assert excinfo.value.code == "bad_policy"


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


def _register_footprints(client: TestClient) -> str:
    features = [
        {"type": "Feature", "properties": {"name": label}, "geometry": geom.__geo_interface__}
        for label, geom in (
            ("valid", VALID),
            ("bowtie", BOWTIE),
            ("sliver", SLIVER),
            ("dup", DUP_VERTEX),
        )
    ]
    payload = json.dumps({"type": "FeatureCollection", "features": features}).encode()
    name = _test_name()
    response = _post(
        client,
        payload=payload,
        filename=f"{name}.geojson",
        kind="footprint_ai",
        name=name,
        extra={"is_synthetic": "true"},
    )
    assert response.status_code == 201, response.text
    source_id = response.json()["source_id"]
    loaded = client.post(f"/sources/{source_id}/load")
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["loaded"] == 4, loaded.text
    return source_id


def test_load_flags_and_health_summary(db: Session, api: tuple[TestClient, MemoryStore]) -> None:
    client, _store = api
    source_id = _register_footprints(client)

    summary = client.post(f"/sources/{source_id}/load").json()
    assert summary["qc"] == {
        "flagged_features": 3,
        "by_flag": {"invalid_geometry": 1, "sliver_area": 2, "duplicate_vertex": 1},
    }

    health = client.get(f"/sources/{source_id}/health").json()
    assert health["loaded"]["features"] == 4
    assert health["loaded"]["by_class"] == {"building": 4}
    assert health["qc"] == summary["qc"]

    rows = db.query(SourceFeature).filter(SourceFeature.source_id == health["source_id"]).all()
    assert len(rows) == 4
    per_feature = sorted(tuple(row.qc_flags) for row in rows)
    assert per_feature == [
        (),
        ("duplicate_vertex",),
        ("invalid_geometry", "sliver_area"),
        ("sliver_area",),
    ]

    # A reload must refresh flags through the upsert, not leave the old ones behind.
    again = client.post(f"/sources/{source_id}/load")
    assert again.status_code == 200, again.text
    assert again.json()["qc"] == summary["qc"]
    assert client.get(f"/sources/{source_id}/health").json()["qc"] == summary["qc"]
