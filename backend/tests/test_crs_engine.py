"""CRS engine unit tests: transformations, model selection, residuals, blunders.

These run without a database: they only exercise pyproj, the model ladder and the
report, which is where the numbers shown by the UI come from.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pytest
from shapely.geometry import Point

from app.crs.errors import CrsError
from app.crs.rubber_sheet import ControlPoint, select_model, transform_xy
from app.crs.service import feature_class_for
from app.crs.transform import build_transformation

_XS = [0.0, 100.0, 200.0, 300.0, 0.0, 100.0, 200.0, 300.0, 50.0, 250.0]
_YS = [0.0, 0.0, 0.0, 0.0, 200.0, 200.0, 200.0, 200.0, 100.0, 100.0]

Mapper = Callable[[float, float], tuple[float, float]]


def _pairs(mapper: Mapper) -> list[ControlPoint]:
    points: list[ControlPoint] = []
    for index, (x, y) in enumerate(zip(_XS, _YS, strict=True)):
        tx, ty = mapper(x, y)
        points.append(ControlPoint(index=index, source=(x, y), target=(tx, ty), label=f"cp{index}"))
    return points


def _affine(x: float, y: float) -> tuple[float, float]:
    return (2.0 + 1.02 * x - 0.03 * y, -5.0 + 0.01 * x + 0.98 * y)


def _poly2(x: float, y: float) -> tuple[float, float]:
    return (x + 0.0005 * (x - 150.0) ** 2, y + 0.0004 * (y - 100.0) ** 2 + 0.0003 * x * y)


def _warp(x: float, y: float) -> tuple[float, float]:
    """A localized bump: no global polynomial captures it, a spline can."""
    bump = 12.0 * math.exp(-(((x - 150.0) ** 2) + ((y - 150.0) ** 2)) / 2000.0)
    ax, ay = _affine(x, y)
    return (ax + bump, ay - 0.4 * bump)


def _dense_pairs(mapper: Mapper) -> list[ControlPoint]:
    """A 7x7 grid, so a local distortion has enough neighbours to be resolved."""
    points: list[ControlPoint] = []
    index = 0
    for i in range(7):
        for j in range(7):
            x, y = float(i * 50), float(j * 50)
            tx, ty = mapper(x, y)
            points.append(
                ControlPoint(index=index, source=(x, y), target=(tx, ty), label=f"g{index}")
            )
            index += 1
    return points


def _fit(points: list[ControlPoint]):
    return select_model(
        points, min_control_points=4, blunder_sigma=3.5, blunder_floor=0.5, unit="m"
    )


def test_pipeline_names_the_operation_and_reprojects_chandigarh() -> None:
    transformation = build_transformation("EPSG:4326", "EPSG:32643")

    assert transformation.pipeline.startswith("+proj=pipeline")
    x, y = transformation.transformer.transform(76.773, 30.733)

    assert math.isclose(x, 669744.1249, abs_tol=0.01)
    assert math.isclose(y, 3401354.6667, abs_tol=0.01)

    projected = transformation.apply(Point(76.773, 30.733))
    assert math.isclose(projected.x, x, abs_tol=1e-9)
    assert math.isclose(projected.y, y, abs_tol=1e-9)


def test_unknown_crs_is_refused_with_a_code() -> None:
    with pytest.raises(CrsError) as excinfo:
        build_transformation("EPSG:999999", "EPSG:32643")

    assert excinfo.value.code == "invalid_crs"


def test_exact_affine_data_picks_the_affine_model() -> None:
    report = _fit(_pairs(_affine))

    assert report.model == "affine"
    assert report.n_control == 10
    assert report.rmse_m < 1e-6
    assert report.max_resid_m < 1e-6
    assert [entry.model for entry in report.models] == ["affine", "poly2", "tps"]
    assert all(entry.available for entry in report.models)
    scores = {entry.model: entry.loo_rmse for entry in report.models}
    assert scores["affine"] is not None and scores["affine"] < 1e-6


def test_quadratic_distortion_beats_a_straight_fit() -> None:
    report = _fit(_pairs(_poly2))

    scores = {entry.model: entry.loo_rmse for entry in report.models}
    assert report.model == "poly2"
    assert scores["affine"] is not None and scores["poly2"] is not None
    assert scores["poly2"] < scores["affine"]


def test_local_warp_is_not_left_to_a_global_fit() -> None:
    report = _fit(_dense_pairs(_warp))

    scores = {entry.model: entry.loo_rmse for entry in report.models}
    assert report.model == "tps"
    assert scores["tps"] is not None and scores["affine"] is not None
    assert scores["tps"] < scores["affine"]


def test_a_blunder_point_is_flagged_not_absorbed() -> None:
    points = _pairs(_affine)
    bad = points[5]
    points[5] = ControlPoint(
        index=bad.index,
        source=bad.source,
        target=(bad.target[0] + 5.0, bad.target[1] + 5.0),
        label="bad",
    )

    report = _fit(points)

    assert len(report.blunders) == 1
    assert report.blunders[0]["index"] == 5
    assert report.blunder_threshold_m >= 0.5
    flagged = {
        entry["index"]
        for entry in report.residuals
        if entry["residual"] > report.blunder_threshold_m
    }
    assert flagged == {5}


def test_too_few_control_points_is_refused() -> None:
    with pytest.raises(CrsError) as excinfo:
        _fit(_pairs(_affine)[:3])

    assert excinfo.value.code == "insufficient_control_points"
    assert excinfo.value.status == 422


def test_collinear_control_points_are_refused() -> None:
    collinear = [
        ControlPoint(index=i, source=(float(i * 10.0), 0.0), target=(float(i * 10.0), 1.0))
        for i in range(8)
    ]

    with pytest.raises(CrsError) as excinfo:
        _fit(collinear)

    assert excinfo.value.code in {"no_fittable_model", "insufficient_control_points"}


def test_the_fitted_model_maps_sources_onto_targets() -> None:
    points = _pairs(_poly2)
    report = _fit(points)
    model_params = report.params["model_params"]

    sources = np.array([list(p.source) for p in points], dtype=np.float64)
    mapped = transform_xy(report.model, model_params, sources)

    for row, point in zip(mapped, points, strict=True):
        assert math.isclose(float(row[0]), point.target[0], abs_tol=1e-6)
        assert math.isclose(float(row[1]), point.target[1], abs_tol=1e-6)


@pytest.mark.parametrize(
    ("kind", "geometry", "expected"),
    [
        ("cadastral", "Polygon", "parcel"),
        ("revenue", "MultiPolygon", "parcel"),
        ("footprint_ai", "Polygon", "building"),
        ("municipal", "LineString", "road"),
        ("utility", "LineString", "utility_line"),
        ("gnss", "Point", "gnss_point"),
        ("revenue", "Point", "point"),
        ("cadastral", "GeometryCollection", "other"),
    ],
)
def test_feature_classes_follow_the_documented_mapping(
    kind: str, geometry: str, expected: str
) -> None:
    assert feature_class_for(kind, geometry) == expected
