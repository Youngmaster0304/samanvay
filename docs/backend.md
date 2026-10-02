# backend.md

Working title for the product in these files: **Samanvay** (समन्वय, "coordination, harmonization"). Rename freely. Read `research.md` first for the reasoning; this file is the build spec.

Tags: **[N]** = behaviour taken from the NAKSHA reconciliation protocol described in the Frontiers paper (confirm against the SOP). **[P]** = starting prior or heuristic that must be calibrated on our own data before we quote it.

## 1. Architecture

```
            ┌────────────┐   files / APIs
 sources ──►│  Ingest    │──► object store (COG, GPKG, CSV)  + source_registry
            └─────┬──────┘
                  ▼
            ┌────────────┐
            │  Normalize │  CRS engine, GCP rubber-sheeting, schema mapping, LGD codes
            └─────┬──────┘
                  ▼
            ┌────────────┐
            │  Extract   │  AI footprints (precomputed) + polygon QC
            └─────┬──────┘
                  ▼
            ┌────────────┐
            │  Match     │  offset estimate → blocking → pair scoring → assignment → split/merge
            └─────┬──────┘
                  ▼
            ┌────────────┐
            │  Topology  │  validate + bounded repair
            └─────┬──────┘
                  ▼
            ┌────────────┐
            │  Resolve   │  NAKSHA tiers, source hierarchy, human queue
            └─────┬──────┘
                  ▼
            ┌────────────┐
            │  Score     │  confidence + reasons, field-queue priority
            └─────┬──────┘
                  ▼
   PostGIS canonical layer ──► OGC API Features / platform API / exports / webhooks
```

Design rules:
1. **Append-only history.** Source observations and decisions are never overwritten. A resolution references the observations it used. Re-running with a different policy must be possible without re-ingesting.
2. **Never invent geometry.** Resolution selects one source's actual geometry, or sends the case to a human. No averaging of boundaries.
3. **Every automated action is logged** with inputs, parameters, before/after and a reason code.
4. **Explainable outputs.** Every score carries its component values.
5. **Federated by design.** One instance per ULB or state; nothing assumes a national database.

## 2. Stack

| Concern | Choice | Note |
|---|---|---|
| API | Python 3.12, FastAPI, Pydantic v2 | You already use FastAPI. |
| DB | PostgreSQL with PostGIS | Canonical store. Spatial indexes (GiST). |
| Jobs | Celery with Redis | One task per pipeline stage, resumable. |
| Object store | MinIO (S3 API) | COG rasters, exports, uploads. |
| Raster tiles | TiTiler serving COGs | Dynamic tiles for the map, no pre-tiling. |
| Vector tiles | Martin or pg_tileserv from PostGIS | Verify the current release you pick. |
| Geo libs | rasterio, GDAL, pyproj, shapely 2, geopandas | STRtree for blocking. |
| ML | PyTorch for training (Colab/Kaggle), ONNX Runtime for CPU inference | Heavy runs off your laptop. |
| Matching model | LightGBM or scikit-learn gradient boosting | Small, fast, explainable via feature importance. |
| Text | rapidfuzz, a small multilingual embedding model, an Indic transliteration library | Verify library maintenance status before committing. |
| OGC API | pygeoapi or a thin FastAPI implementation of `/collections`, `/items` | Keep it minimal and conformant. |
| Tests | pytest, hypothesis | Property tests for topology repair. |
| Packaging | Docker Compose | postgis, redis, minio, api, worker, titiler, tileserver, web. |

Hardware note: 16 GB RAM and no discrete GPU **[from your notes]**. Keep the demo AOI to about 1 to 3 km², use COG windowed reads, precompute extraction on Colab, run everything else CPU-only.

## 3. Repository layout

```
samanvay/
├── backend/
│   ├── app/api/            routers: sources, layers, runs, features, conflicts, queue, export, ogc
│   ├── app/core/           config, auth, audit, policy loader
│   ├── app/domain/         Pydantic models, enums, reason codes
│   ├── app/ingest/         connectors: cog, geojson, gpkg, shp, csv_gnss, csv_ror
│   ├── app/crs/            engine.py, gcp.py (rubber-sheet), residuals.py
│   ├── app/extract/        onnx_infer.py, regularize.py, polygon_qc.py
│   ├── app/match/          offset.py, blocking.py, features.py, scorer.py, assign.py, splitmerge.py
│   ├── app/topology/       rules.py, repair.py
│   ├── app/attributes/     schema_match.py, normalize.py, translit.py, lgd.py
│   ├── app/change/         vector_change.py, (raster_change.py stretch)
│   ├── app/resolve/        policy.py, tiers.py, hierarchy.py, queue.py
│   ├── app/confidence/     components.py, scorer.py, calibration.py
│   ├── app/fieldqueue/     priority.py, routing.py
│   ├── app/eval/           metrics.py, experiments/ (offset, match, topology, extraction)
│   └── app/workers/        celery tasks per stage
├── db/migrations/
├── data/                   manifests only; big files stay out of git
├── policies/               naksha_default.yaml (tolerances, hierarchy, thresholds)
├── docs/
└── tests/
```

## 4. Data model (PostGIS)

Keep everything in one CRS for storage, a metric CRS chosen per AOI (a UTM zone or the state's projected CRS), and reproject on output. Store `srid` explicitly.

```sql
-- provenance
CREATE TABLE source_registry (
  source_id      uuid PRIMARY KEY,
  name           text NOT NULL,
  kind           text NOT NULL,   -- drone_ori | satellite | dsm | dtm | cadastral | revenue | municipal | utility | gnss | footprint_ai | footprint_ref
  authority      text,
  licence        text,
  url            text,
  vintage        date,
  sha256         text,
  is_synthetic   boolean NOT NULL DEFAULT false,   -- must be true for any generated data
  sigma_m        double precision,                 -- assumed 1-sigma positional accuracy [P]
  crs_original   text,
  ingested_at    timestamptz DEFAULT now()
);

CREATE TABLE source_feature (               -- append-only observations
  obs_id         uuid PRIMARY KEY,
  source_id      uuid REFERENCES source_registry,
  feature_class  text NOT NULL,             -- parcel | building | road | utility_line | gnss_point
  geom           geometry(Geometry, 32646),  -- example SRID; choose per AOI
  raw_props      jsonb,
  extractor_conf double precision,          -- for AI-derived features
  qc_flags       text[],
  created_at     timestamptz DEFAULT now()
);
CREATE INDEX ON source_feature USING gist (geom);

CREATE TABLE transform_log (                -- CRS/rubber-sheet steps with residuals
  id uuid PRIMARY KEY, source_id uuid, pipeline text, n_control int,
  rmse_m double precision, max_resid_m double precision, params jsonb, created_at timestamptz DEFAULT now()
);

-- matching and resolution
CREATE TABLE match_pair (
  pair_id uuid PRIMARY KEY, obs_a uuid, obs_b uuid,
  score double precision, features jsonb, relation text,  -- one_to_one | split | merge | none
  run_id uuid
);

CREATE TABLE canonical_feature (
  cid            uuid PRIMARY KEY,
  feature_class  text,
  geom           geometry(Geometry, 32646),
  chosen_obs     uuid REFERENCES source_feature,       -- geometry always comes from one observation
  ulpin          text,                                  -- linked or validated, never issued by us
  status         text,                                  -- auto_resolved | needs_review | dispute | accepted | rejected
  confidence     double precision, grade char(1), reasons jsonb,
  lgd_village    text, lgd_ulb text,
  valid_from     timestamptz, valid_to timestamptz
);
CREATE INDEX ON canonical_feature USING gist (geom);

CREATE TABLE conflict (
  conflict_id uuid PRIMARY KEY, cid uuid REFERENCES canonical_feature,
  type text,            -- area_out_of_tolerance | position | overlap | gap | attribute | split_merge | encroachment_candidate
  evidence jsonb,       -- distances, areas, source ids, image chips
  recommended_obs uuid, tier smallint, state text, created_at timestamptz DEFAULT now()
);

CREATE TABLE decision (                     -- every resolution, human or automatic
  decision_id uuid PRIMARY KEY, conflict_id uuid, actor text, action text,
  chosen_obs uuid, reason_code text, note text, params jsonb, created_at timestamptz DEFAULT now(),
  prev_hash text, hash text                 -- optional hash chain [stretch]
);

-- field queue
CREATE TABLE field_task (
  task_id uuid PRIMARY KEY, cid uuid, priority double precision,
  reason text[], cluster_id int, assigned_to text, state text,   -- open | assigned | surveyed | closed
  gt_point uuid REFERENCES source_feature
);

-- personal data kept apart from geometry
CREATE TABLE owner_record (
  cid uuid, owner_name_enc bytea, owner_name_translit text, share text, tenure text, record_ref text
);   -- never returned by feature APIs; purpose-bound endpoint only
```

## 5. Pipeline stages and algorithms

### 5.1 Ingest
- Accept COG (convert with GDAL if not COG), GeoJSON, GeoPackage, Shapefile, CSV (GNSS points, RoR).
- Validate CRS. Reject files with no CRS unless the user supplies one explicitly; log that choice.
- Write a `source_registry` row with licence, vintage, checksum, `is_synthetic`.
- Hash the file. Same hash = idempotent re-ingest.

### 5.2 CRS and georeferencing
- Use `pyproj` to build the transformation between source and target CRS; store the PROJ pipeline string in `transform_log`.
- **Sheet georeferencing** (legacy scans): user or algorithm supplies control point pairs (image xy to ground xy). Fit a ladder of models: affine, 2nd-order polynomial, thin-plate spline. Choose by leave-one-out RMSE, not by fit RMSE. Report residuals per control point. Flag any point whose residual exceeds a threshold (blunder detection). **[N]** for the spline/polynomial rubber-sheeting idea.
- Keep the transform reversible where possible, and always store parameters.

### 5.3 Extraction and polygon QC
- Inference: ONNX model on ORI tiles (512 or 1024 px with overlap), stitched, thresholded, vectorized, regularized (orthogonalization of near-right angles, simplification within a small tolerance).
- Precompute on Colab and import via `POST /extractions` to keep the demo machine light.
- **Polygon QC**: features such as area, compactness, solidity, edge straightness, mean model confidence, overlap with other candidates, relation to nDSM height if available, fraction of vegetation pixels. Start with hand-set rules; optionally train a small classifier on your reference labels. Output: `qc_flags` and a keep/review/drop recommendation. (Idea inspired by the polygon-level QC study cited in `research.md`.)

### 5.4 Offset estimation
```
input: layers A (reference) and B, candidate pairs with IoU >= 0.5 or centroid distance <= d0
1. compute displacement vectors (centroid_B - centroid_A) for confident pairs
2. robust estimate: median vector, then MAD-based outlier rejection, then re-estimate
3. optionally fit a low-order (affine) field if residual has spatial structure (Moran's I on residuals)
4. apply correction to B, log (dx, dy, bearing, n_pairs, residual_rmse)
5. re-run matching on corrected B
```
Report the correction in metres and bearing in the UI. Do not silently shift a department's layer: store the corrected copy as a new observation with a link to the original.

### 5.5 Matching
1. **Blocking:** STRtree over B; for each A feature, candidates within `search_radius` (default 15 m [P], scale with source sigma).
2. **Pair features:** IoU; intersection over min-area; centroid distance; area ratio; Hausdorff distance; orientation difference; shape (compactness) difference; attribute similarity (survey number exact/fuzzy, ward/village code equal, transliterated owner similarity if permitted).
3. **Scorer:** v0 weighted sum with logistic squashing. v1 LightGBM trained on hand-labeled pairs from your AOI (200 to 300 labels).
4. **Assignment:** solve 1-to-1 with the Hungarian algorithm on cost = 1 − score; accept if score ≥ `accept_threshold` (default 0.6 [P]).
5. **Split/merge:** for unmatched features with strong partial overlap to a common neighbour, group them. One-to-many where the sum of parts covers ≥ 85% of the whole [P] is a split or a merge.
6. Store every pair with feature values for later explanation.

### 5.6 Topology
Rules:
- Parcels: no overlaps larger than `overlap_tol` (default 0.05 m² or 0.1% of area [P]); no gaps smaller than `sliver_tol` between neighbouring parcels unless the gap is a mapped road; no self-intersections; valid rings.
- Buildings: contained by a parcel or flagged `building_crosses_boundary`.
- Utility lines: no dangles under `dangle_tol` (1 m [P]) unless at a declared endpoint; no undershoot or overshoot at junctions.

Repair policy (bounded):
- `make_valid` for invalid rings, then recheck area change ≤ 1% [P].
- Snap vertices within `snap_tol` (default 0.10 m [P]) to a neighbour's vertex or edge. Never move a vertex further than `snap_tol`.
- Refuse and raise a conflict when repair would change area by more than the bound, or when multiple repair options exist.
- Property test: repair never increases the number of violations, never moves any vertex further than `snap_tol`, and never changes area beyond the bound.

### 5.7 Attribute mapping
- Column matching: score = max of (fuzzy name similarity, embedding similarity of names plus sample values, data-type and value-pattern compatibility). Output a crosswalk with the winning signal and score per column, editable by a human.
- Value normalization: trim, case-fold, unify numerals, map land-use classes to a controlled vocabulary, normalize area units (acre, cent, guntha, kanal, sq.m., etc.; keep the original string and the converted value).
- Transliteration between Devanagari/regional scripts and Latin for fuzzy owner or village matching. Keep original strings.
- LGD join for state/district/village/ULB codes. Keep both code and name.
- **Recorded-vs-geodesic area** is a first-class comparison: `area_recorded` vs `ST_Area(geom)` (geodesic or in an equal-area or local metric CRS), with the relative difference stored.

### 5.7b Change detection
- **Vector change** between the previous canonical layer (or legacy layer) and the new one: unchanged, moved (offset-aware after 5.4), modified shape, new, removed, split, merged.
- **Encroachment candidates:** change touching land flagged as government or public (from the reference layer) → conflict type `encroachment_candidate` with wording "candidate for verification".
- Raster change (stretch): requires two image epochs; use a siamese or difference-plus-classifier approach on a co-registered pair. Report co-registration error first.

### 5.8 Conflict resolution policy

Configured in `policies/naksha_default.yaml`. **[N]** items follow the tiers described in `research.md`; confirm exact values.

```yaml
area_tolerance_pct: 5.0                 # [N] |A_drone − A_recorded| / A_recorded
position_tol_sigma: 3.0                 # multiples of combined sigma [P]
source_hierarchy: [gnss_gt, drone_ori_derived, municipal, revenue_legacy]   # default precedence
require_possession_evidence: true       # boundary supported by imagery edge or a GT point
autoresolve_min_confidence: 70          # [P]
```

Decision procedure per matched feature:
```
Tier 1  (auto):   area within tolerance
                  AND positional disagreement ≤ position_tol_sigma × combined sigma
                  AND no topology violation left after bounded repair
                  AND possession evidence present
                  → adopt the drone-derived geometry as authoritative [N]; status auto_resolved.
Tier 2  (human):  anything else → status dispute/needs_review; conflict record with evidence;
                  goes to the reviewer queue and to the field queue if a GNSS check would settle it. [N]
Hierarchy:        when two sources disagree and no tier-1 rule applies, recommend the higher-ranked
                  source, but require review if the lower-ranked source has independent corroboration.
```
Every decision writes `decision` with reason code (for example `T1_AREA_OK`, `T2_AREA_OOT`, `T2_OVERLAP`, `H_GNSS_WINS`, `HUMAN_ACCEPT_A`).

### 5.9 Confidence scoring

Per canonical feature, components in [0, 1]:

| Component | Meaning | Sketch |
|---|---|---|
| S_pos | Positional agreement after offset correction | exp(−(d/σ)²), d = distance between chosen and corroborating geometry, σ = combined source sigma |
| S_src | Reliability of the chosen source | prior from `sigma_m`, later updated from review outcomes |
| S_corr | Independent corroboration | 0 for single source, rising with the number of independent agreeing sources |
| S_topo | Topology validity | 1 if clean, lower if repaired, 0 if unresolved violation |
| S_attr | Attribute agreement | share of key attributes that agree (survey number, ward, land use) |
| S_ext | Extractor confidence and QC | model confidence and polygon QC outcome for AI-derived features |

```
score = 100 × (0.30·S_pos + 0.20·S_src + 0.15·S_corr + 0.15·S_topo + 0.10·S_attr + 0.10·S_ext)   [P]
caps:  unresolved topology violation → ≤ 40;  open conflict → ≤ 60;  single-source → ≤ 75
grade: A ≥ 85 | B 70–84 | C 55–69 | D 40–54 | E < 40
```
All weights, caps and grade bands are **starting heuristics**. Calibrate by plotting score against hand-labeled correctness (reliability diagram) and adjusting. Never present these grades as official accuracy classes. Store all components in `reasons` JSON so the UI can explain any score.

Source sigma priors [P]: GNSS/CORS ≈ 0.03 m; drone-derived ≈ 0.1 to 0.15 m; AI footprints ≈ 0.3 to 2 m; municipal ≈ 1 to 5 m; revenue legacy ≈ 5 to 30 m; utilities ≈ 1 to 10 m. These follow the rough ranges in a public repo's table and general expectations, so replace them with values measured on your AOI.

### 5.10 Field-queue priority

```
priority = 0.45·(1 − confidence/100)
         + 0.20·conflict_severity          # dispute > overlap > attribute
         + 0.15·neighbour_dispute_density  # disputes cluster
         + 0.10·change_flag                # new/changed building
         + 0.10·gt_gap                     # no GNSS point within 30 m
```
Then cluster tasks spatially (DBSCAN with ~150 m radius [P]) and order clusters by nearest-neighbour route from the assigned surveyor's start point. Output per task: map location, why it was picked, what to measure. When a surveyor returns a GNSS point, ingest it as `gnss_gt`, re-run matching for that cell, and close or re-open the conflict.

## 6. API

Two surfaces. Both versioned under `/v1`.

**OGC API - Features** (read-only, for other departments):
- `GET /ogc/collections`
- `GET /ogc/collections/{parcels|buildings|conflicts}/items?bbox=&limit=&filter=`
- `GET /ogc/collections/{id}/items/{fid}`
Owner and personal fields are **never** present here.

**Platform API**:

| Method and path | Purpose |
|---|---|
| `POST /sources` | Register and upload a source with licence and `is_synthetic` |
| `DELETE /sources/{id}` | Owner cleanup: removes the row, its features, matches and stored bytes |
| `GET /sources`, `GET /sources/{id}/health` | List, plus CRS residuals, coverage and schema summary |
| `POST /runs` | Start harmonization for an AOI with a policy version |
| `GET /runs/{id}` | Stage progress, timings, counts, errors |
| `GET /features/{cid}` | Canonical feature with score, reasons, chosen source and all alternatives |
| `GET /conflicts?state=&type=&bbox=` | Reviewer queue |
| `POST /conflicts/{id}/decision` | Accept A, accept B, edit, defer, with reason code |
| `GET /queue/field` | Ranked field tasks |
| `POST /queue/field/{id}/gnss` | Submit a GT point |
| `GET /exports/{geojson|gpkg}` | Reconciled layer plus decision log |
| `GET /eval` | Stored experiment results with limits attached |
| `POST /webhooks` | Subscribe by AOI, feature class, change type, minimum confidence |
| `POST /purpose/owner-lookup` | Purpose-bound, audit-logged access to owner data |

Errors use RFC 7807 problem responses. Every write endpoint is idempotent by client-supplied key.

## 7. Security and data protection
- OIDC or JWT auth with roles: viewer, reviewer, supervisor, admin. Row scoping by ULB.
- Owner data lives in `owner_record`, encrypted at rest, excluded from the feature and OGC surfaces, reachable only through a purpose-bound endpoint that logs who, why and when.
- Audit log is append-only. Optional hash chain on `decision` rows (stretch).
- Uploads: size limits, MIME and extension checks, GDAL run in a constrained worker.
- Secrets in env or a secrets manager, never in the repo.
- Follow current DPDP Act obligations and any state data policy. **Confirm the legal text before making compliance statements.** **[B]**

## 8. Evaluation module

Implement the experiments in `datasets.md` §9 as runnable scripts, storing results in a table with AOI size, hardware, commit hash and date:
- offset recovery (known shifts),
- match precision/recall on hand-labeled pairs,
- topology repair counts and manual audit sample,
- extractor F1/IoU before and after regularization, and QC flag precision,
- manual-versus-tool timing on a small subset.

The UI's "Evaluation" page reads these rows. Every metric shows its limits next to it.

## 9. Testing
- Unit tests on each algorithm with small hand-built geometries.
- Property tests (hypothesis) for repair bounds and idempotence.
- Golden-file test: fixed small AOI produces the same canonical layer given the same policy.
- Contract tests: API responses validate against the shared TypeScript types.
- Performance check: pipeline on the demo AOI completes in a few minutes on CPU.

## 10. Build order
1. Compose stack, migrations, source registry, ingest for GeoJSON/GPKG/COG.
2. CRS engine and rubber-sheet with residuals.
3. Import precomputed extractions and polygon QC.
4. Offset estimation, blocking, scoring, assignment. Hand-label pairs early.
5. Topology rules and bounded repair with property tests.
6. Policy engine (tiers, hierarchy), conflicts, decisions.
7. Confidence and reasons.
8. OGC API and platform API.
9. Field queue and GNSS return loop.
10. Evaluation scripts and page.
11. Stretch: nDSM and LOD1, raster change, webhooks, hash chain.

## 11. What the backend must not do
- Issue or claim to issue official ULPINs.
- Determine legal ownership or title.
- Average boundaries.
- Use synthetic data without `is_synthetic = true` and a visible UI label.
- Return owner personal data through general APIs.
