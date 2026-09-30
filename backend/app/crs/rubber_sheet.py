"""Control-point rubber-sheeting for sheet georeferencing (backend.md §5.2).

A ladder of models is fitted to the control pairs — affine, second-order polynomial,
thin-plate spline — and the winner is chosen by **leave-one-out RMSE**, not by fit RMSE,
so a flexible model cannot win by overfitting. Every control point gets a residual, and
points whose residual exceeds a policy threshold are flagged as blunders instead of being
quietly absorbed into the transform.

Coordinates: `source` is the as-registered position (image/sheet coordinates, or the
distorted position of a vector layer) and `target` is the true ground position. Both are
in the same planar system as the storage CRS (metres) for the thresholds to mean metres;
the report states the unit it was given.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.crs.errors import CrsError

FloatArray = NDArray[np.float64]

MODEL_ORDER: tuple[str, ...] = ("affine", "poly2", "tps")
"""Least flexible first: ties in leave-one-out RMSE resolve towards the simpler model."""

_LOO_MIN: dict[str, int] = {"affine": 4, "poly2": 7, "tps": 4}
"""Points needed before leave-one-out still leaves a fittable fold for that model."""

_COMPLEXITY: dict[str, int] = {"affine": 0, "poly2": 1, "tps": 2}

_SELECTION_EPSILON = 1e-6
"""Leave-one-out scores within this of the best are a tie: differences below it are
numerical noise, so a tie resolves towards the simpler model."""

_ROBUST_K = 1.4826  # normal-consistent scale factor: MAD -> sigma


@dataclass(frozen=True)
class ControlPoint:
    """One control pair: as-registered position, true ground position."""

    index: int
    source: tuple[float, float]
    target: tuple[float, float]
    label: str | None = None


@dataclass(frozen=True)
class ModelResult:
    """What one candidate model did: whether it could be fitted, and how it scored."""

    model: str
    available: bool
    reason: str | None
    loo_rmse: float | None
    fit_rmse: float | None


@dataclass(frozen=True)
class GeorefReport:
    """Model selection plus the residuals that justify the choice."""

    model: str
    n_control: int
    models: list[ModelResult]
    residuals: list[dict[str, Any]]
    rmse_m: float
    loo_rmse_m: float | None
    max_resid_m: float
    blunder_threshold_m: float
    blunders: list[dict[str, Any]]
    params: dict[str, Any]
    unit: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "n_control": self.n_control,
            "unit": self.unit,
            "models": [
                {
                    "model": m.model,
                    "available": m.available,
                    "reason": m.reason,
                    "loo_rmse": m.loo_rmse,
                    "fit_rmse": m.fit_rmse,
                }
                for m in self.models
            ],
            "rmse": self.rmse_m,
            "loo_rmse": self.loo_rmse_m,
            "max_residual": self.max_resid_m,
            "blunder_threshold": self.blunder_threshold_m,
            "blunders": self.blunders,
            "residuals": self.residuals,
            "params": self.params,
        }


def select_model(
    points: list[ControlPoint],
    *,
    min_control_points: int,
    blunder_sigma: float,
    blunder_floor: float,
    unit: str = "m",
) -> GeorefReport:
    """Fit the ladder, pick by leave-one-out RMSE, flag blunders, return the report."""
    if len(points) < min_control_points:
        raise CrsError(
            "insufficient_control_points",
            f"{len(points)} control points given; the policy requires at least "
            f"{min_control_points}",
        )

    src = np.array([p.source for p in points], dtype=np.float64)
    dst = np.array([p.target for p in points], dtype=np.float64)
    if not np.isfinite(src).all() or not np.isfinite(dst).all():
        raise CrsError("non_finite_control_point", "control points must be finite numbers")

    results: list[ModelResult] = []
    loo_by_model: dict[str, float] = {}
    for model in MODEL_ORDER:
        result = _score_model(model, src, dst)
        results.append(result)
        if result.available and result.loo_rmse is not None:
            loo_by_model[model] = result.loo_rmse

    if not loo_by_model:
        raise CrsError(
            "no_fittable_model",
            "no model in the ladder (affine, poly2, tps) could be leave-one-out scored "
            "with these control points; add spread-out points or check the coordinates",
        )

    best = min(loo_by_model.values())
    tied = [name for name, score in loo_by_model.items() if score <= best + _SELECTION_EPSILON]
    winner = min(tied, key=lambda name: _COMPLEXITY[name])
    params = _fit(winner, src, dst)
    fitted = _predict(winner, params, src)

    # Blunders are judged on leave-one-out residuals: an interpolating model (tps) fits
    # every control point exactly, so only how well the *other* points predict this one
    # says anything about whether the point itself is trustworthy.
    residuals: list[dict[str, Any]] = []
    fit_lengths: list[float] = []
    loo_lengths: list[float] = []
    for i, point in enumerate(points):
        dx = float(fitted[i, 0] - dst[i, 0])
        dy = float(fitted[i, 1] - dst[i, 1])
        fit_length = math.hypot(dx, dy)
        fold = _fit(winner, np.delete(src, i, axis=0), np.delete(dst, i, axis=0))
        loo_point = _predict(winner, fold, src[i : i + 1])[0]
        loo_dx = float(loo_point[0] - dst[i, 0])
        loo_dy = float(loo_point[1] - dst[i, 1])
        loo_length = math.hypot(loo_dx, loo_dy)
        fit_lengths.append(fit_length)
        loo_lengths.append(loo_length)
        residuals.append(
            {
                "index": point.index,
                "label": point.label,
                "source": [point.source[0], point.source[1]],
                "target": [point.target[0], point.target[1]],
                "dx": dx,
                "dy": dy,
                "residual": fit_length,
                "loo_dx": loo_dx,
                "loo_dy": loo_dy,
                "loo_residual": loo_length,
            }
        )

    rmse = _rmse(np.array(fit_lengths, dtype=np.float64))
    threshold, robust_sigma = _blunder_threshold(
        np.array(loo_lengths, dtype=np.float64), blunder_sigma, blunder_floor
    )
    blunders = [
        {"index": row["index"], "label": row["label"], "residual": row["loo_residual"]}
        for row in residuals
        if row["loo_residual"] > threshold
    ]

    return GeorefReport(
        model=winner,
        n_control=len(points),
        models=results,
        residuals=residuals,
        rmse_m=rmse,
        loo_rmse_m=loo_by_model[winner],
        max_resid_m=max(fit_lengths) if fit_lengths else 0.0,
        blunder_threshold_m=threshold,
        blunders=blunders,
        params={
            "model_params": params,
            "robust_sigma": robust_sigma,
            "selection": "leave_one_out_rmse",
            "residual_basis": "leave_one_out",
        },
        unit=unit,
    )


def transform_xy(model: str, params: dict[str, Any], xy: FloatArray) -> FloatArray:
    """Apply a fitted model to an (n, 2) array: as-registered -> true position."""
    return _predict(model, params, xy)


# --- model machinery -------------------------------------------------------


def _score_model(model: str, src: FloatArray, dst: FloatArray) -> ModelResult:
    n = len(src)
    if n < _LOO_MIN[model]:
        return ModelResult(
            model=model,
            available=False,
            reason=f"needs at least {_LOO_MIN[model]} control points, got {n}",
            loo_rmse=None,
            fit_rmse=None,
        )
    if not _has_full_rank(model, src):
        return ModelResult(
            model=model,
            available=False,
            reason="control points are degenerate for this model (rank deficient)",
            loo_rmse=None,
            fit_rmse=None,
        )

    fold_errors: list[float] = []
    try:
        for i in range(n):
            fold_src = np.delete(src, i, axis=0)
            fold_dst = np.delete(dst, i, axis=0)
            if not _has_full_rank(model, fold_src):
                return ModelResult(
                    model=model,
                    available=False,
                    reason="a leave-one-out fold is rank deficient for this model",
                    loo_rmse=None,
                    fit_rmse=None,
                )
            params = _fit(model, fold_src, fold_dst)
            predicted = _predict(model, params, src[i : i + 1])
            fold_errors.append(float(np.hypot(*(predicted[0] - dst[i]))))

        fitted = _predict(model, _fit(model, src, dst), src)
    except (np.linalg.LinAlgError, ValueError, CrsError) as exc:
        # Duplicated anchors, collinear control geometry, or a solve that will not hold.
        return ModelResult(
            model=model,
            available=False,
            reason=f"the fit is singular for this control geometry ({type(exc).__name__})",
            loo_rmse=None,
            fit_rmse=None,
        )

    in_sample = [float(np.hypot(*(fitted[i] - dst[i]))) for i in range(n)]
    return ModelResult(
        model=model,
        available=True,
        reason=None,
        loo_rmse=_rmse(np.array(fold_errors, dtype=np.float64)),
        fit_rmse=_rmse(np.array(in_sample, dtype=np.float64)),
    )


def _design(model: str, xy: FloatArray) -> FloatArray:
    x, y = xy[:, 0], xy[:, 1]
    if model == "affine":
        return np.column_stack([np.ones_like(x), x, y])
    if model == "poly2":
        return np.column_stack([np.ones_like(x), x, y, x * x, x * y, y * y])
    raise ValueError(f"no polynomial design for model {model!r}")


def _normalize(src: FloatArray) -> tuple[FloatArray, FloatArray, float]:
    """Shift to the control-point centroid and scale into a unit box.

    Design matrices built from raw UTM coordinates (x ~ 6.7e5, x*x ~ 4.5e11) lose rank to
    rounding, and the r^2 log r spline kernel becomes ill-conditioned there, so every fit
    runs in this unit frame and the origin and scale travel with the parameters.
    """
    origin = src.mean(axis=0) if len(src) else np.zeros(2, dtype=np.float64)
    spread = float(np.max(np.abs(src - origin))) if len(src) else 1.0
    scale = spread if spread > 0 else 1.0
    return (src - origin) / scale, origin, scale


def _has_full_rank(model: str, src: FloatArray) -> bool:
    normalized, _origin, _scale = _normalize(src)
    if model == "tps":
        # A thin-plate spline needs three non-collinear anchors.
        return int(np.linalg.matrix_rank(_design("affine", normalized))) == 3
    design = _design(model, normalized)
    return int(np.linalg.matrix_rank(design)) == int(design.shape[1])


def _fit(model: str, src: FloatArray, dst: FloatArray) -> dict[str, Any]:
    normalized, origin, scale = _normalize(src)
    if model in {"affine", "poly2"}:
        coefficients, *_ = np.linalg.lstsq(_design(model, normalized), dst, rcond=None)
        return {
            "coefficients": coefficients.tolist(),
            "origin": origin.tolist(),
            "scale": scale,
        }
    params = _fit_tps(normalized, dst)
    params["origin"] = origin.tolist()
    params["scale"] = scale
    return params


def _predict(model: str, params: dict[str, Any], xy: FloatArray) -> FloatArray:
    origin = np.array(params["origin"], dtype=np.float64)
    normalized = (xy - origin) / float(params["scale"])
    if model in {"affine", "poly2"}:
        coefficients = np.array(params["coefficients"], dtype=np.float64)
        return _design(model, normalized) @ coefficients
    return _predict_tps(params, normalized)


def _tps_kernel(a: FloatArray, b: FloatArray) -> FloatArray:
    """U(r) = r^2 log r for the 2D thin-plate spline, with U(0) = 0."""
    delta = a[:, None, :] - b[None, :, :]
    r2 = np.einsum("ijk,ijk->ij", delta, delta).astype(np.float64, copy=False)
    out: FloatArray = np.zeros_like(r2, dtype=np.float64)
    positive = r2 > 0
    out[positive] = r2[positive] * np.log(r2[positive]) / 2.0
    return out


def _fit_tps(src: FloatArray, dst: FloatArray) -> dict[str, Any]:
    n = len(src)
    polynomial = _design("affine", src)
    system = np.zeros((n + 3, n + 3), dtype=np.float64)
    system[:n, :n] = _tps_kernel(src, src)
    system[:n, n:] = polynomial
    system[n:, :n] = polynomial.T

    rhs = np.zeros((n + 3, 2), dtype=np.float64)
    rhs[:n] = dst
    try:
        solution = np.linalg.solve(system, rhs)
    except np.linalg.LinAlgError as exc:  # degenerate control geometry
        raise CrsError(
            "singular_control_geometry",
            "the control points are collinear or duplicated, so a thin-plate spline "
            "cannot be fitted; remove duplicates or add spread-out points",
        ) from exc
    return {
        "weights": solution[:n].tolist(),
        "polynomial": solution[n:].tolist(),
        "anchors": src.tolist(),
    }


def _predict_tps(params: dict[str, Any], xy: FloatArray) -> FloatArray:
    weights = np.array(params["weights"], dtype=np.float64)
    polynomial = np.array(params["polynomial"], dtype=np.float64)
    anchors = np.array(params["anchors"], dtype=np.float64)
    smooth = _tps_kernel(xy, anchors) @ weights
    return _design("affine", xy) @ polynomial + smooth


def _rmse(values: FloatArray) -> float:
    if values.size == 0:
        return 0.0
    return float(math.sqrt(float(np.mean(values**2))))


def _blunder_threshold(
    residuals: FloatArray, sigma_multiple: float, floor: float
) -> tuple[float, float]:
    """Robust threshold: k x (MAD-derived sigma), never below an absolute floor."""
    if residuals.size == 0:
        return floor, 0.0
    median = float(np.median(residuals))
    mad = float(np.median(np.abs(residuals - median)))
    sigma = _ROBUST_K * mad
    return max(sigma_multiple * sigma, floor), sigma
