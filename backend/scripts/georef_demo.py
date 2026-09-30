"""Stage 3 demo: rubber-sheet a synthetically distorted sheet against known truth.

Run from `backend/` with compose up:

    python scripts/georef_demo.py

Three parts, printed in order:

1. the model ladder (affine / poly2 / thin-plate spline) scored by leave-one-out RMSE on
   control points taken from a *known* distortion, including one deliberately bad point
   that must come back flagged as a blunder;
2. the same kind of fit driven through the real HTTP endpoints on a synthetic source,
   so the stored report and the loaded feature can be read back from the API;
3. a measured check: how far the loaded polygon sits from the truth, compared with how
   far it sat there before the correction.

Everything it registers is named `__stage3demo__*`, flagged `is_synthetic`, and removed
again at the end (registry rows cascade to features and the transform log; the uploaded
object is deleted from the bucket directly).
"""

from __future__ import annotations

import json
import math
import os
import sys
import urllib.request
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("POLICY_PATH", str(REPO_ROOT / "policies" / "naksha_default.yaml"))

import numpy as np  # noqa: E402
from pyproj import Transformer  # noqa: E402
from shapely import wkt  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.policy import get_policy  # noqa: E402
from app.crs.rubber_sheet import ControlPoint, select_model  # noqa: E402
from app.crs.service import georef_policy  # noqa: E402
from app.db.models import SourceRegistry  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

API = "http://localhost:8000"
DEMO_PREFIX = "__stage3demo__"
SEED = 20260930  # fixed: the demo prints the same numbers on every run

_TO_4326 = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)
_FROM_4326 = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


def _grid() -> np.ndarray:
    xs = np.arange(669600.0, 670300.0, 120.0)
    ys = np.arange(3401000.0, 3401700.0, 120.0)
    return np.array([[x, y] for x in xs for y in ys], dtype=np.float64)


def _distort(xy: np.ndarray) -> np.ndarray:
    """Known synthetic distortion: 0.4 deg rotation, 1.0008 scale, one 6 m bump."""
    theta = math.radians(0.4)
    scale = 1.0008
    cx, cy = 669950.0, 3401350.0
    dx = xy[:, 0] - cx
    dy = xy[:, 1] - cy
    xs = cx + scale * (math.cos(theta) * dx - math.sin(theta) * dy)
    ys = cy + scale * (math.sin(theta) * dx + math.cos(theta) * dy)
    bump = 6.0 * np.exp(-(((xs - cx) ** 2) + ((ys - cy) ** 2)) / 200_000.0)
    return np.column_stack([xs + bump, ys - 0.5 * bump])


def print_ladder() -> dict[str, object]:
    policy = get_policy(os.environ["POLICY_PATH"])
    limits = georef_policy(policy)
    truth = _grid()
    distorted = _distort(truth)
    points = [
        ControlPoint(
            index=i,
            source=(float(distorted[i, 0]), float(distorted[i, 1])),
            target=(float(truth[i, 0]), float(truth[i, 1])),
            label=f"cp{i:02d}",
        )
        for i in range(len(truth))
    ]
    # A survey point recorded 5 m off, at a location of its own: it must be flagged,
    # not averaged into the fit.
    bad = np.array([669660.0, 3401060.0])
    points.append(
        ControlPoint(
            index=len(points),
            source=(float(bad[0]), float(bad[1])),
            target=(float(bad[0]) + 5.0, float(bad[1]) - 4.0),
            label="bad-survey",
        )
    )

    print("== 1. model ladder on a known synthetic distortion ==")
    print(
        f"policy: min_control_points={limits.min_control_points} "
        f"blunder_sigma={limits.blunder_sigma} blunder_floor_m={limits.blunder_floor_m}"
    )
    print(f"control points: {len(points)} (one labelled bad-survey)")

    report = select_model(
        points,
        min_control_points=limits.min_control_points,
        blunder_sigma=limits.blunder_sigma,
        blunder_floor=limits.blunder_floor_m,
        unit="m",
    ).as_dict()

    print(f"{'model':8} {'available':10} {'loo_rmse':>12} {'fit_rmse':>12}  reason")
    for entry in report["models"]:
        loo = "-" if entry["loo_rmse"] is None else f"{entry['loo_rmse']:.4f}"
        fit = "-" if entry["fit_rmse"] is None else f"{entry['fit_rmse']:.4f}"
        print(
            f"{entry['model']:8} {entry['available']!s:10} {loo:>12} {fit:>12}  "
            f"{entry['reason'] or ''}"
        )
    print(
        f"selected: {report['model']}  rmse={report['rmse']:.4f} m  "
        f"loo_rmse={report['loo_rmse']:.4f} m  max_residual={report['max_residual']:.4f} m"
    )
    print(
        f"blunder threshold: {report['blunder_threshold']:.4f} m "
        f"(robust sigma {report['params']['robust_sigma']:.4f}, "
        f"basis {report['params']['residual_basis']})"
    )
    for blunder in sorted(report["blunders"], key=lambda row: -row["residual"]):
        print(
            f"  FLAGGED {blunder['label']} index={blunder['index']} "
            f"loo_residual={blunder['residual']:.3f} m"
        )
    labels = [blunder["label"] for blunder in report["blunders"]]
    assert report["model"] in {"poly2", "tps"}, (
        "a nonlinear distortion must not be left to a straight fit",
        report,
    )
    assert "bad-survey" in labels, report
    worst = max(report["blunders"], key=lambda row: row["residual"])
    assert worst["label"] == "bad-survey", worst
    return report


def _call(method: str, path: str, body: object = None) -> dict[str, object]:
    request = urllib.request.Request(API + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, data, timeout=60) as response:
        return json.load(response)


def _upload(payload: bytes, filename: str, name: str) -> dict[str, object]:
    boundary = uuid.uuid4().hex
    fields = {"name": name, "kind": "municipal", "licence": "ODbL-1.0", "is_synthetic": "true"}
    body = b""
    for key, value in fields.items():
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
        ).encode()
    body += (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/geo+json\r\n\r\n"
    ).encode()
    body += payload + f"\r\n--{boundary}--\r\n".encode()

    request = urllib.request.Request(
        API + "/sources",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _parcel_truth() -> np.ndarray:
    return np.array(
        [
            [669700.0, 3401100.0],
            [669900.0, 3401100.0],
            [670100.0, 3401100.0],
            [670100.0, 3401300.0],
            [670100.0, 3401500.0],
            [669900.0, 3401500.0],
            [669700.0, 3401500.0],
            [669700.0, 3401300.0],
        ],
        dtype=np.float64,
    )


def _distorted_geojson() -> bytes:
    truth = _parcel_truth()
    ring = [tuple(_TO_4326.transform(x, y)) for x, y in _distort(truth)]
    ring.append(ring[0])
    document = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": f"{DEMO_PREFIX} distorted parcel"},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        ],
    }
    return json.dumps(document).encode()


def _control_pairs() -> list[dict[str, object]]:
    truth = _parcel_truth()
    distorted = _distort(truth)
    return [
        {
            "from": [float(distorted[i, 0]), float(distorted[i, 1])],
            "to": [float(truth[i, 0]), float(truth[i, 1])],
            "label": f"corner{i}",
        }
        for i in range(len(truth))
    ]


def _centroid_error(geom_xy: np.ndarray, truth: np.ndarray) -> float:
    corner = truth.mean(axis=0)
    measured = geom_xy.mean(axis=0)
    return float(np.hypot(*(measured - corner)))


def print_end_to_end() -> None:
    print("\n== 2. the same fit through the HTTP endpoints ==")
    name = f"{DEMO_PREFIX} synthetic distorted sheet {uuid.uuid4().hex[:8]}"
    registered = _upload(_distorted_geojson(), "distorted.geojson", name)
    source_id = str(registered["source_id"])
    print(f"registered synthetic source {source_id} (is_synthetic={registered['is_synthetic']})")

    fit = _call("POST", f"/sources/{source_id}/georef", {"pairs": _control_pairs(), "unit": "m"})
    print(
        f"fit: model={fit['model']} n_control={fit['n_control']} "
        f"rmse={fit['rmse']:.4f} m max_residual={fit['max_residual']:.4f} m "
        f"transform_log={fit['transform_log_id']}"
    )
    for entry in fit["models"]:
        loo = "-" if entry["loo_rmse"] is None else f"{entry['loo_rmse']:.4f}"
        print(f"  {entry['model']:6} loo_rmse={loo:>10} available={entry['available']}")

    loaded = _call("POST", f"/sources/{source_id}/load")
    print(
        f"load: loaded={loaded['loaded']} by_class={loaded['by_class']} "
        f"srid={loaded['storage_srid']} georef_applied={loaded['georef_applied']}"
    )

    health = _call("GET", f"/sources/{source_id}/health")
    print(
        f"health: features={health['loaded']['features']} "
        f"declared_crs={health['declared_crs']} "
        f"transform={health['transform']['pipeline'] if health['transform'] else None}"
    )

    truth = _parcel_truth()
    with SessionLocal() as session:
        row = session.get(SourceRegistry, uuid.UUID(source_id))
        assert row is not None
        object_key = row.object_key
        geometry = session.execute(
            text("SELECT ST_AsText(geom) FROM source_feature WHERE source_id = :sid"),
            {"sid": uuid.UUID(source_id)},
        ).scalar_one()
        session.delete(row)
        session.commit()

    from app.core.objectstore import get_object_store

    get_object_store().remove_object(os.environ.get("MINIO_BUCKET", "samanvay"), object_key)

    ring = np.array(wkt.loads(geometry).exterior.coords)
    corrected = ring[:-1] if tuple(ring[0]) == tuple(ring[-1]) else ring
    before = _centroid_error(_distort(truth), truth)
    after = _centroid_error(corrected, truth)
    print(
        f"measured: polygon corner error before correction={before:.3f} m, "
        f"after correction={after:.3f} m"
    )
    print(f"cleaned up: removed source {source_id}, its features, log rows and object bytes")


def main() -> int:
    np.random.seed(SEED)
    try:
        print_ladder()
        print_end_to_end()
    except Exception as exc:  # a demo prints its failure and exits non-zero
        print(f"demo failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
