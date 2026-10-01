"""Pure-function tests for the Stage 4 scorer, pair features and assignment.

No database: geometry helpers, the logistic scorer, attribute similarity and
the Hungarian assignment (including the swap case greedy gets wrong) are
exercised directly.
"""

from __future__ import annotations

from shapely.geometry import Polygon

from app.matching.service import (
    _attribute_similarity,
    _score,
    assign_hungarian,
    pair_features,
)

WEIGHTS = {
    "iou": 3.0,
    "iom": 1.5,
    "distance": -2.0,
    "area_ratio": 1.0,
    "orientation": -1.0,
    "compactness": -1.0,
    "attribute": 1.5,
}
BIAS = -1.5


def _square(west: float, south: float, east: float, north: float) -> Polygon:
    return Polygon([(west, south), (east, south), (east, north), (west, north), (west, south)])


def test_pair_features_for_a_near_miss_pair() -> None:
    # Two 40 m squares offset by 10 m: IoU = 0.6, centroids 10 m apart.
    a = _square(0, 0, 40, 40)
    b = _square(10, 0, 50, 40)
    features = pair_features(a, b, {}, {}, radius=15.0)

    assert 0.59 < features["iou"] < 0.61
    assert 9.9 < features["distance_m"] < 10.1
    assert 0.6 < features["distance"] < 0.71  # normalised by the radius
    assert features["area_ratio"] == 1.0
    assert features["orientation"] == 0.0
    assert features["compactness"] == 0.0
    assert features["attribute"] == 0.0


def test_pair_features_catches_a_rotated_pair() -> None:
    a = _square(0, 0, 40, 10)
    rotated = _square(0, 0, 10, 40)
    features = pair_features(a, rotated, {}, {}, radius=15.0)

    assert features["orientation"] > 0.9  # 90 deg difference / 90
    assert features["iou"] < 0.3


def test_scorer_is_monotonic_and_bounded() -> None:
    good = {
        "iou": 0.9,
        "iom": 0.95,
        "distance": 0.1,
        "area_ratio": 0.95,
        "orientation": 0.0,
        "compactness": 0.0,
        "attribute": 0.8,
    }
    mediocre = dict(good, iou=0.4, iom=0.5, distance=0.6, attribute=0.2)
    bad = dict.fromkeys(WEIGHTS, 0.0) | {"distance": 1.0}

    score_good = _score(good, WEIGHTS, BIAS)
    score_mediocre = _score(mediocre, WEIGHTS, BIAS)
    score_bad = _score(bad, WEIGHTS, BIAS)

    assert 0.0 < score_bad < score_mediocre < score_good < 1.0
    assert score_good >= 0.6
    assert score_bad < 0.6


def test_attribute_similarity_prefers_exact_values() -> None:
    assert _attribute_similarity({"survey_no": "12"}, {"survey_no": "12"}) == 1.0
    assert _attribute_similarity({"osm_id": 7}, {"osm_id": 7}) == 1.0
    fuzzy = _attribute_similarity({"name": "Himalaya Marg"}, {"name": "Himalay Marg"})
    assert 0.7 < fuzzy < 1.0
    assert _attribute_similarity({"a": "x"}, {"b": "y"}) == 0.0


def test_hungarian_beats_greedy_on_the_swap_case() -> None:
    # Greedy takes a1-b1 (0.90) and strands a2 (b1 is used, a2-b2 does not
    # exist); Hungarian finds the better total: a1-b2 (0.85) + a2-b1 (0.80).
    candidates = [
        ("a1", "b1", {"x": 1.0}, 0.90),
        ("a1", "b2", {"x": 1.0}, 0.85),
        ("a2", "b1", {"x": 1.0}, 0.80),
    ]

    accepted, fallbacks = assign_hungarian(candidates, accept=0.6)

    assert fallbacks == 0
    pairs = {(fid_a, fid_b) for _, fid_a, fid_b, _ in accepted}
    assert pairs == {("a1", "b2"), ("a2", "b1")}
    assert all(score >= 0.6 for score, _, _, _ in accepted)


def test_assignment_respects_the_accept_threshold() -> None:
    candidates = [("a1", "b1", {"x": 1.0}, 0.4)]

    accepted, fallbacks = assign_hungarian(candidates, accept=0.6)

    assert accepted == [] and fallbacks == 0
