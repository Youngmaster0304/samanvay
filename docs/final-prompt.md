# final-prompt.md

Paste the block below into Claude Code (or Cursor) at the root of an empty repo. Put `research.md`, `datasets.md`, `backend.md`, `front.md` and `design.md` in `/docs` first. The agent reads them; the prompt does not repeat them.

Use the follow-up prompts in the second section one stage at a time. Do not ask for the whole product in one go.

---

## Master prompt

```
You are a senior geospatial backend engineer and product-minded frontend engineer. We are building a working prototype for Smart India Hackathon 2026, problem statement 26013: "Automated Integration and Intelligent Harmonization of Multi-source Geospatial Data for Urban Land Record Management" (Ministry of Rural Development, Department of Land Resources, NAKSHA programme). Working title: Samanvay.

READ FIRST, in this order, before writing any code:
1. docs/research.md   what the problem really is, verified facts, what to build and not build
2. docs/backend.md    architecture, data model, algorithms, policy, API
3. docs/front.md      screens, components, data contracts
4. docs/design.md     design system, tokens, anti-vibe-coding rules
5. docs/datasets.md   data sources, licences, evaluation experiments

Summarize back to me in under 200 words what you will build and what you will NOT build, then wait for my go-ahead.

PRODUCT IN ONE SENTENCE
A harmonization engine and reviewer workbench that aligns drone-derived, AI-extracted, cadastral, revenue, municipal, utility and GNSS layers; matches features across them; applies the NAKSHA three-tier reconciliation policy (area tolerance, dispute/anomaly flagging, field verification); scores every output with an explainable confidence; and produces a risk-ranked field-verification queue and a reconciled layer exposed through OGC API Features.

NON-NEGOTIABLE RULES
1. Honesty. Never fabricate data, metrics, users, testimonials, partners or results. Every dataset has a row in source_registry with licence, vintage and checksum. Synthetic data must have is_synthetic = true and a visible SYNTHETIC label in the UI. Every number shown in the UI must come from the backend.
2. Never invent geometry. Resolution selects one source's actual geometry or sends the case to a human. Never average boundaries.
3. Automated repairs are bounded, logged and refusable. Property-test them.
4. Do not claim legal title determination or official ULPIN issuance. ULPIN is a linked/validated field only.
5. Owner personal data lives in a separate table, is excluded from feature and OGC APIs, and is reachable only through a purpose-bound, audit-logged endpoint.
6. Confidence weights, thresholds, tolerances and source sigmas are starting heuristics marked [P] in backend.md. Implement them as configuration in policies/naksha_default.yaml, not hard-coded, and build the calibration and evaluation scripts.
7. Hardware is 16 GB RAM with no discrete GPU. Keep the demo AOI to about 1 to 3 km2, use COG windowed reads, treat ML extraction as an offline precomputed import (I will run it on Colab), and keep everything else CPU-only.
8. Follow design.md exactly for the UI: warm paper and ink neutrals, marigold as the single brand colour, NO blue and NO purple anywhere, Source Serif 4 plus IBM Plex (not Inter, Geist or Space Grotesk), no gradients in the chrome, no glassmorphism, no emoji, no decorative icons, no left-edge colour stripes, no three-feature-card sections, no fake dashboards or browser frames, no skeleton loaders, minimal motion that respects prefers-reduced-motion. Never rely on colour alone.
9. Accessibility is a requirement: keyboard-operable queue, visible focus, semantic HTML, list equivalent for the map, axe checks in CI.
10. If a spec is ambiguous or two files disagree, stop and ask me one concise question rather than guessing.

STACK (see backend.md and front.md for detail)
Backend: Python 3.12, FastAPI, Pydantic v2, PostgreSQL + PostGIS, Celery + Redis, MinIO, rasterio/GDAL/pyproj/shapely 2/geopandas, LightGBM, pytest + hypothesis. Tiles: TiTiler for COG, a vector tile server from PostGIS. Frontend: Next.js (App Router) + TypeScript strict, MapLibre GL JS, TanStack Query, Zustand + URL state, Tailwind driven by CSS variable tokens from design.md, Radix or React Aria primitives, next-intl (English + Hindi), Vitest, Playwright, axe. Docker Compose for everything.

DELIVERY PLAN (one stage at a time; stop after each stage and report)
Stage 0  Repo scaffold, docker compose (postgis, redis, minio, api, worker, titiler, tileserver, web), CI, lint, type-check, migrations, design tokens as CSS variables, health endpoints.
Stage 1  Ingest + source registry (COG, GeoJSON, GeoPackage, Shapefile, CSV) with CRS validation and checksums.
Stage 2  CRS engine + control-point rubber-sheeting with model selection by leave-one-out RMSE, residual report and blunder flags.
Stage 3  Import of precomputed AI footprints + polygon QC flags.
Stage 4  Offset estimation, blocking, pair features, scorer, Hungarian assignment, split/merge detection. Includes a labeling helper for hand-labeled pairs.
Stage 5  Topology rules + bounded repair with property tests.
Stage 6  Policy engine (NAKSHA tiers, hierarchy), conflicts, decisions with reason codes.
Stage 7  Confidence scoring with stored components and caps, grade A to E.
Stage 8  API: platform API + OGC API Features, RFC 7807 errors, idempotency keys.
Stage 9  Frontend shell, map canvas, layers panel, modes, feature inspector.
Stage 10 Conflict queue + evidence card + keyboard flow + undo.
Stage 11 Field queue (mobile-first) + GNSS return loop.
Stage 12 Overview, Sources, Runs, Changes, Evaluation, Exports, About/Privacy/Terms/Contact.
Stage 13 Evaluation scripts (offset recovery, match precision/recall, topology audit, extraction QC, manual vs tool timing) and the Evaluation page with a non-empty "what this does not show" for every result.
Stage 14 Accessibility, responsive and design-review pass using the checklist in design.md section 12.

DEFINITION OF DONE FOR EACH STAGE
- Code compiles, type-checks, lints clean; tests pass.
- Migrations run from scratch.
- A short docs/stage-N.md notes what was built, what was not, known limitations, and how to run it.
- No dead code, unused components or leftover template assets.
- You have run it and show me the actual output (command, response or screenshot), not a description of what it should do.

START NOW with the summary from the first paragraph of this prompt. Do not write code yet.
```

---

## Follow-up prompts (use one at a time)

**Approve and start Stage 0**
```
Summary approved. Do Stage 0 only. Use the tokens from design.md verbatim. When done, run the compose stack and show me the health endpoints and the web shell rendering with the paper background and marigold primary button. Then stop.
```

**Data acquisition (you run parts of this yourself)**
```
Write data_acquisition/ scripts for the datasets bundle I choose (Bundle B in datasets.md). Each script must: fetch or document the manual download, verify the checksum, clip to the AOI, convert rasters to COG, and append a source_registry manifest entry with licence and attribution. Do not include any data in git. Flag every dataset whose licence you could not confirm from its official page.
```

**Extraction notebook for Colab**
```
Create notebooks/extract_footprints.ipynb that I can run on Colab: load ORI tiles from a COG, run a pretrained or lightly fine-tuned building segmentation model, vectorize and regularize, compute the polygon QC features from backend.md 5.3, and export GeoPackage plus a manifest. Report F1 and IoU against the reference footprints before and after regularization. Do not claim numbers you did not compute.
```

**Simulated legacy sheet (labeled)**
```
Build a script that takes reference footprints and produces a SIMULATED legacy cadastral sheet: apply a documented distortion (rotation, scale, thin-plate warp), rasterize it as a scan-like image, and store the true transform as ground truth. Mark the resulting source is_synthetic = true. Then use it to test the georeferencing engine and report the recovered-versus-true error.
```

**Design review pass**
```
Run the design review in design.md section 12 against every implemented screen. List each violation with file and line, fix them, and re-run axe. Then produce screenshots of the workbench at 360, 768, 1440 and 1920 px widths and check for overflow.
```

**Demo script**
```
Write docs/demo-script.md: a 5-minute fixed walkthrough using only real screens and real numbers from the evaluation table. Include the "what this does not do" statement and the data provenance statement. No claims that are not backed by a stored result.
```
