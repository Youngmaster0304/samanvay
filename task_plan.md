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


## Free-tier upgrade: user uploads -> plain-English card -> satellite map (2026-10-01)

### P0 — Upload + dataset card — DONE
- [x] `web/src/lib/sources.ts`: `uploadSource` (multipart POST /sources), `fetchSourceHealth`,
      `fetchSourceFeatures`, `describeSource` (plain-English lines, no invented numbers),
      kind/format/CRS labels fixed (footprint_ai/ref, dsm, dtm; drop nonexistent ai_extracted),
      `KIND_HEX` palette for MapLibre
- [x] `web/src/components/upload-source.tsx`: collapsible upload panel (file, name, kind,
      licence, authority, vintage, declared CRS, sigma, synthetic flag)
- [x] `web/src/components/dataset-card.tsx`: registry lines + health lines (loaded counts,
      QC flags, last transform)
- [x] `web/src/app/(app)/sources/page.tsx`: upload panel, post-upload success card,
      click-a-row expansion to the dataset card

### P1 — Registry layers on the satellite map — DONE
- [x] backend: `GET /sources/{id}/features.geojson` (ST_AsGeoJSON(ST_Transform(geom, 4326)),
      props = feature_class/qc_flags/extractor_conf/raw props, limit, empty collection when
      unloaded, 404 unknown source) + 3 tests in `test_sources_api.py`
- [x] `web/src/components/map-canvas.tsx`: dynamic GeoJSON sources with fill/line/circle per
      layer, visibility toggles, union fit-bounds
- [x] `web/src/app/(app)/map/page.tsx`: registry group in the layers sidebar, skips rasters
      and the two OSM sources already drawn statically
- [x] tests: `web/tests/sources.test.ts` (describeSource, labels, hex palette)

### Gates — DONE
- [x] backend: ruff check / format --check / mypy / pytest (80 tests) green
- [x] web: lint / typecheck / vitest (22 tests) / next build green

### Next
- [ ] P2: sample drone flight script (synthetic orthophoto + precomputed footprint_ai), seed prod
- [ ] push + live verify (upload from UI, features.geojson 200, map layer visible)

### P1b — Raster preview (rasters drawn honestly, no fake elevation) — DONE
- [x] backend: `app/ingest/preview.py` (WGS 84 bounds via `warp_bounds`, RGB PNG through
      rasterio's MemoryFile PNG driver, 2-98% percentile stretch for non-uint8, average
      downsample to <=1200 px) + `GET /sources/{id}/preview` (bounds/width/height/png) and
      `GET /sources/{id}/preview.png` (Cache-Control 1h); 404 `no_preview` for vectors,
      404 `source_not_found`, 404 `preview_bytes_missing` when object storage was reset,
      422 `preview_needs_crs`; +3 tests in `test_sources_api.py` (91 total)
- [x] web: `fetchSourcePreview`/`previewPngUrl`, MapCanvas `imageLayers` (image source
      TL,TR,BR,BL + raster layer, refs synced in effects, per-layer visibility), map page
      image rows in the Registry group + fit-bounds union, dataset-card raster health line
      ("drawn from its preview PNG")

### P2 — Sample drone flight — DONE
- [x] `backend/scripts/demo_drone_flight.py`: synthetic 1 m/px RGB GeoTIFF (noise terrain,
      soft park greens, OSM roads widened into asphalt strips, OSM buildings rasterised with
      per-roof colours + cast shadow; WGS 84 geoms reprojected to EPSG:32643 first) and a
      60-feature jittered OSM `footprint_ai` subset (seed 2026, original ring kept when the
      jitter invalidates it); reuse-by-name via `POST /sources`; `--build-only` smoke path;
      verified locally: 1581x1510 px, preview PNG rendered and visually checked (road grid,
      roofs, parks all present - first attempt forgot transform_geom and drew nothing; fixed)
- [x] about page wording: synthetic demo orthophoto IS ingested/drawn; real ORI/cadastral/
      revenue/utility still honestly "not ingested"

### Gates (both stacks, post-P1b+P2)
- [x] backend: ruff check / format --check / mypy (54 files) / pytest 91 - green
- [x] web: lint / typecheck / vitest 22 / next build 8 routes - green

### Remaining
- [ ] commit + push (deploy Render + Vercel), live-verify preview endpoints
- [ ] seed production: `SAMANVAY_API=https://samanvay-api-wjkk.onrender.com uv run python scripts/demo_drone_flight.py`
- [ ] live verify: features.geojson 200, preview.png 200, registry + raster rows on map

### Deploy + live verification - DONE (2026-10-01)
- [x] commit `37db6f5` pushed -> Render redeployed (new `/sources/{id}/preview` route answers
      `source_not_found` for unknown ids = new build live), Vercel /sources returns 200
- [x] seeded prod: ortho `141a5edf-bf6a-49fe-9406-5bfbc26eb4b4` (5,384,047 B, raster=True,
      synthetic=True, coverage in file coords EPSG:32643), footprints
      `2c66a7d1-2737-4053-b265-b8cee450a0cb` (60 features, QC 0 flags), 8 sources total
- [x] `GET /preview` -> bounds [76.76296, 30.72612, 76.77972, 30.73997] (WGS 84), 1581x1510
- [x] `GET /preview.png` -> 1,950,804 B, PNG magic 89 50 4e 47
- [x] `GET /features.geojson` -> 60 features, first coord 76.774, 30.731 (WGS 84)
- [x] `/readyz` all green (db/redis/object_store/policy); web /sources 200
- [x] dataset card now embeds the preview `<img>` for raster sources (web gates green after)
