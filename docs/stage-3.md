# Stage 3 — CRS engine + rubber-sheeting (plan Stage 2)

Status: **complete**, all gates green, live evidence captured.

## What was built

| Piece | File | What it does |
| --- | --- | --- |
| CRS transformation | `backend/app/crs/transform.py` | `build_transformation` → pyproj transformer with the PROJ pipeline string; refuses unknown CRS as `invalid_crs` |
| Rubber-sheeting ladder | `backend/app/crs/rubber_sheet.py` | affine → 2nd-order polynomial → thin-plate spline, selected by **leave-one-out RMSE** with a complexity tie-break; MAD-based blunder flags on LOO residuals; control coordinates normalised (centroid + unit scale) before any fit |
| Service | `backend/app/crs/service.py` | `fit_georef`, `latest_georef`, `load_features` (reproject once → apply fitted correction → idempotent upsert), `source_health`, class mapping |
| Errors | `backend/app/crs/errors.py` | `CrsError(IngestError)` — refusals carry a code and message, never fabricated geometry |
| API | `backend/app/api/georef.py` | `POST|GET /sources/{id}/georef`, `POST /sources/{id}/load`, `GET /sources/{id}/health` |
| Auto-load | `backend/app/ingest/service.py` | a successful ingest immediately loads features (failure recorded as a registry note, never fatal) |
| Policy | `policies/naksha_default.yaml` | `georef:` block — `min_control_points`, `blunder_sigma`, `blunder_floor_m` (all [P]) |
| Migration | `0003_features_and_transforms.py` | `source_feature` (storage SRID, gist index, unique `(source_id, source_fid)`), `transform_log`; FKs `ON DELETE CASCADE` |
| Object store | `backend/app/ingest/store.py` | `ObjectStore.get()` on MinIO + in-memory test double |

## Decisions worth knowing

- **Blunders are flagged from leave-one-out residuals**, not in-sample ones: an
  interpolating TPS fits every control point exactly, so only a fold that *excludes* a
  point can reveal that the point disagrees with its neighbours.
- **Coordinates are normalised inside the fit.** Raw UTM values (x ≈ 6.7e5) made the
  polynomial design matrix rank-deficient by rounding and the spline kernel ill-conditioned
  (LOO ≈ 1e14 m). The origin/scale travel with the stored parameters.
- **Selection uses an epsilon tie-break** (`_SELECTION_EPSILON = 1e-6`): exact-affine data
  gives LOO ≈ 1e-13 for every model, and the simplest model must win such a tie.
- Registry CRS overrides pyogrio's reading; reprojection happens exactly once, then the
  fitted correction is applied **forward** (control pairs are as-registered → true).

## Verification

Gates: `ruff check` · `ruff format --check` (58 files) · `mypy app` (48 files) ·
`pytest -q` → **80 passed** (17 CRS unit tests, 6 georef API tests, 3 conflict tests + Stage 0/1 suites).

Live evidence:

- Both pilot sources loaded into EPSG:32643 via `POST /sources/{id}/load`
  (494 OSM road features, 1 municipal boundary feature).
- `scripts/georef_demo.py` (synthetic 0.4° rotation + 1.0008 scale + 6 m bump, 37 control
  points including one labelled `bad-survey`):

```text
model    available      loo_rmse     fit_rmse  reason
affine   True             2.4728       2.2523
poly2    True             2.2117       1.8481   <- selected
tps      True             3.2039       0.0000
blunder threshold: 0.9388 m (robust sigma 0.2682, basis leave_one_out)
  FLAGGED bad-survey index=36 loo_residual=12.086 m   <- worst residual is the bad point
...
measured: polygon corner error before correction=5.360 m, after correction=0.000 m
```

The measured corner error comes from reading the stored geometry back with `ST_AsText`
after the HTTP load — not from the fit's own report.

## Bugs found and fixed while verifying

1. **Double reprojection** — `load_features` reprojected an already-registered-CRS frame
   again. Removed the `to_crs`; the registry row alone decides.
2. **Upsert no-op** — `on_conflict_do_update(set_={"geom": SourceFeature.geom})` wrote
   `SET geom = conflict.geom` (self-assignment), so a corrected geometry never replaced the
   auto-loaded one. Now `statement.excluded.*`; the demo's measured error dropped 5.360 m →
   0.000 m because of this fix.
3. **Attribute-less layers crashed the load** — a GeoJSON with no property columns
   serialises to zero records and `zip(..., strict=True)` raised. Such features now load
   with empty properties, which is what the file actually said.

## Limitations (honest)

- Control points are supplied by the caller; there is no automatic GCP detection.
- Blunder flags are advisory — points are never silently dropped from the fit.
- Raster georeferencing (world files, GCPs on GeoTIFF) is not implemented; vector only.
