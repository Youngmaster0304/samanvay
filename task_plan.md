# task_plan.md — Samanvay build plan (live)

Delivery plan is `docs/final-prompt.md`. Stage numbering here is this repo's own
docs series (`docs/stage-N.md`), with the mapping to the master prompt noted.

## P0 — Stage 3: CRS engine + rubber-sheeting (plan Stage 2) — DONE

- [x] Plan written to `task_plan.md`
- [x] `0003_features_and_transforms` migration: `source_feature` (storage SRID, gist,
      unique `(source_id, source_fid)` for idempotent load) + `transform_log`
- [x] `app/db/models.py`: `SourceFeature`, `TransformLog`
- [x] `app/crs/transform.py`: pyproj transformer, PROJ pipeline string, geometry reprojection
- [x] `app/crs/rubber_sheet.py`: affine / 2nd-order polynomial / thin-plate spline,
      leave-one-out RMSE model selection, per-point residuals, blunder flags (policy-driven)
- [x] `app/crs/service.py`: `fit_georef`, `load_features` (reproject → storage CRS → apply
      fitted correction → upsert observations), report reading
- [x] `policies/naksha_default.yaml`: `georef:` block (min control points, blunder sigma,
      blunder floor)
- [x] API: `POST /sources/{id}/georef`, `GET /sources/{id}/georef`,
      `POST /sources/{id}/load`, `GET /sources/{id}/health`
- [x] ingest auto-loads features after registration (failure recorded as a registry note)
- [x] tests: model selection on known distortions, blunder flagging, pipeline round-trip,
      API contract, idempotent load
- [x] gates: `ruff check`, `ruff format --check`, `mypy app`, `pytest -q`
- [x] live evidence: load the two Sector 22 sources, run `scripts/georef_demo.py`
      (synthetic distortion, labelled), capture output
- [x] `docs/stage-3.md`

## P0 — Stage 4: conflict queue, first slice of plan Stage 6 — DONE

- [x] migration `0004_conflicts`: `conflict` + append-only `conflict_decision`
- [x] detection: PostGIS pair join, overlap / boundary_crossing classification,
      severities from the `conflicts:` policy block
- [x] API: `POST /conflicts/detect`, `GET /conflicts?state=&type=`,
      `POST /conflicts/{id}/decision`
- [x] web: `lib/conflicts.ts` + real `/queue/conflicts` page (detect panel, filters,
      per-row decisions with required reason code)
- [x] tests (3 API flows incl. refusals), gates green both stacks (80 backend / 13 web)
- [x] live evidence: `scripts/conflicts_live_check.py` — 178 pairs → 7 crossings (6 medium,
      1 low) on the real OSM pilot sources; `docs/stage-4-conflicts-1440.png`

## P0 — Stage 5 (repo): polygon QC + matching first slice + demo look — DONE

- [x] plan Stage 3: `app/qc/` (`qc_flags_for`, `qc_limits`), `qc:` policy block; flags stored
  per feature and aggregated in load + health (`invalid_geometry`, `ring_fewer_than_4_points`,
  `sliver_area`, `duplicate_vertex`); `tests/test_qc.py`
- [x] plan Stage 4 first slice: migration `0005_feature_match`, `app/matching/` (IoU scoring,
  greedy 1-to-1 assignment, `matching.max_pairs`), `POST /matches/detect`, `GET /matches`,
  `tests/test_matches_api.py` (scorer, Hungarian, split/merge still open)
- [x] demo look: Esri World Imagery satellite basemap (OSM kept as a toggle), red boundary
  outline, `01 Upload data → 02 Auto-harmonize → 03 Result` strip on overview + map
- [x] live evidence: `scripts/demo_harmonization.py` — QC 3 flags (invalid 1 / sliver 2 /
  dup-vertex 1); match IoU 0.667 assigned from 2 candidates; conflicts 178 pairs → 7 crossings;
  `docs/stage-5-{overview,map}-1440.png`
- [x] gates: backend ruff/format/mypy/pytest exit 0; web lint/typecheck/13 tests/build 7 routes

## P1 — remaining plan stages (not started)

- Plan Stage 4 rest: offset estimation, blocking, pair features, scorer, Hungarian assignment
- Plan Stage 5: topology rules + bounded repair (property tests)
- Plan Stage 6 rest: policy engine (tiers, hierarchy), auto-resolution, canonical reason codes
- Plan Stage 7: confidence scoring
- Plan Stage 8: platform API + OGC API Features
- Frontend follow-ons: map evidence on the queue page, surface
  `/sources/{id}/health` and the georef report in the UI

## Decisions already taken (do not relitigate)

- Next.js 16 + MapLibre; design.md palette wins (no blue/purple); OSM raster basemap (Q1=a);
  live API, no MSW layer; storage CRS EPSG:32643; Chandigarh Sector 22 pilot.
- MapLibre worker pair lives in `web/public/` and must be refreshed on upgrade.
- 360 px screenshots need the iframe harness (headless Edge clamps `--window-size`).
- Rubber-sheet fits run in a normalised (centroid + unit scale) coordinate frame;
  blunder flags use leave-one-out residuals.

## Blockers / risks

- Disk: Docker build cache filled C: once; run `docker builder prune -af` if free < 5 GB.
- Headless WebGL is flaky; re-shoot map screenshots until > 300 KB.
