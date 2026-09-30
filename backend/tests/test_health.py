from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.policy import PolicyError, load_policy


def test_healthz_reports_service_identity(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "samanvay-api"
    assert body["status"] == "ok"
    assert body["version"]
    assert body["storage_srid"] == 32643


def test_readyz_returns_dependency_report(client: TestClient) -> None:
    """Ready is 200 only when every dependency answers; otherwise 503 with detail.

    Running the suite without the compose stack must not fail it, so this asserts
    the shape of the report rather than requiring live services.
    """
    response = client.get("/readyz")
    assert response.status_code in (200, 503)
    body = response.json()
    assert body["status"] in ("ready", "not_ready")
    assert set(body["checks"]) == {"database", "redis", "object_store", "policy"}
    for name, check in body["checks"].items():
        assert "ok" in check, f"check {name} must report ok"
        if not check["ok"]:
            assert check.get("error"), f"failing check {name} must carry an error"


def test_policy_loads_from_yaml(policy_path: Path) -> None:
    bundle = load_policy(policy_path)
    assert bundle.name == "naksha_default"
    assert bundle.version == "0.1.0"
    assert bundle.data["area_tolerance_pct"] == 5.0
    assert bundle.data["source_hierarchy"][0] == "gnss_gt"
    assert set(bundle.data["confidence"]["weights"]) == {
        "pos",
        "src",
        "corr",
        "topo",
        "attr",
        "ext",
    }


def test_policy_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="not found"):
        load_policy(tmp_path / "absent.yaml")
