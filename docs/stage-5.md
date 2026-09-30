# Stage 5 — Polygon QC, matching first slice, demo look (plan Stages 3 and 4)

Date: 2026-09-30. Two plan slices plus the visual pass that makes the demo read like the
target reference: upload → auto-harmonize → result over a tilted satellite scene.

## What landed

### Polygon QC (plan Stage 3)

- `backend/app/qc/` computes flags from the stored geometry alone: `invalid_geometry`,
  `ring_fewer_than_4_points`, `sliver_area`, `duplicate_vertex`. Lines and points never
  receive polygon checks.
- Thresholds live only in `policies/naksha_default.yaml` under `qc:` (`min_polygon_area_m2: 1.0 [P]`).
- `POST /sources/{id}/load` returns `qc: {flagged_features, by_flag}`; the same aggregate is
  added to `GET /sources/{id}/health`; each feature row carries its own `qc_flags` list.

### Matching, first slice (plan Stage 4)

- Migration `0005_feature_match`; `app/matching/service.py` scores polygon∩polygon candidates
  by intersection-over-union (candidates come from the PostGIS intersects index — this slice's
  blocking step) and assigns them greedily, best IoU first, each feature at most once.
- `POST /matches/detect {source_a, source_b}` and `GET /matches?source=`.
- Thresholds from `matching:` — `accept_threshold: 0.60 [P]`, `max_pairs: 5000 [P]`.
- Honest limits: polygon vs polygon only; greedy, not Hungarian (no scipy in the image); no
  attribute/direction/split-merge evidence; disjoint features are not candidates.

### Demo look (web)

- `MapCanvas`: Esri World Imagery satellite basemap (default on, attribution shown), OSM kept
  as a toggleable second basemap with its ODbL line; boundary drawn as a solid `#c4183c`
  (the palette's conflict red) with a white casing so it reads over imagery; pitch 45°, bearing −12°.
- `01 Upload data → 02 Auto-harmonize → 03 Result` pipeline strip on the overview and the map
  page (each step links to its screen).
- Two stale copy lines fixed (sources page, overview "what this run did not check").

## Live evidence

`uv run python scripts/demo_harmonization.py` against `localhost:8000` (idempotent: re-runs
reuse the demo layers by name):

```text
1) QC on an AI-footprint layer (synthetic, flagged in the registry)
   qc: flagged_features 3 — invalid_geometry 1, sliver_area 2, duplicate_vertex 1
   health aggregate identical to the load summary

2) Matching: offset parcel layers -> one IoU assignment
   pairs_examined 2, polygon_candidates 2, assigned 1
   score 0.6667 >= matching.accept_threshold 0.60 (policy naksha_default v0.1.0)
   GET /matches: 1 stored row, method iou_greedy

3) Conflicts on the pilot pair (roads x municipal boundary)
   178 pairs examined -> 7 boundary crossings queued (6 medium, 1 low)
```

Screenshots (headless Edge, 1440×1100):

| File | Shows |
| --- | --- |
| `docs/stage-5-overview-1440.png` | overview with the flow strip, live registry (5 sources, 3 synthetic) |
| `docs/stage-5-map-1440.png` | satellite workbench: layers sidebar, red boundary, roads, Esri attribution |

## Gates (2026-09-30)

| Gate | Result |
| --- | --- |
| `uv run ruff check app tests scripts` / `ruff format --check` | pass / clean |
| `uv run mypy app` | pass (53 files) |
| `uv run pytest -q` | exit 0 (78 test functions; suite shares the live DB) |
| web `npm run lint` / `typecheck` / `test` / `build` | pass / pass / 13 of 13 / 7 routes |
| containers | `samanvay-api` and `samanvay-web` rebuilt and running |
