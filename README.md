# Samanvay (समन्वय)

<p align="center">
  <img src="docs/samanvay-logo.png" alt="Samanvay — Connecting Land Data for Better Cities" width="320">
</p>

A harmonization engine and reviewer workbench for multi-source urban land records.

**Problem:** Smart India Hackathon 2026, problem statement 26013 — *Automated Integration and
Intelligent Harmonization of Multi-source Geospatial Data for Urban Land Record Management*
(Ministry of Rural Development, Department of Land Resources, NAKSHA programme).

Samanvay aligns drone-derived, AI-extracted, cadastral, revenue, municipal, utility and GNSS
layers over one coordinate frame, matches features across them, applies the NAKSHA three-tier
reconciliation policy, scores every output with an explainable confidence, and hands what it
cannot settle to a human with the evidence attached — as a risk-ranked field-verification queue
and a reconciled layer exposed through OGC API Features.

This repository is a **hackathon prototype**. It is not an official DoLR, Survey of India or
NAKSHA system, it does not determine legal title, and it does not issue ULPINs.

## Specifications

Read these before writing or reviewing code:

| File | Contents |
|---|---|
| `docs/research.md` | What the problem really is, verified facts, what to build and not build |
| `docs/backend.md` | Architecture, data model, algorithms, policy, API |
| `docs/front.md` | Screens, components, data contracts |
| `docs/design.md` | Design system, tokens, anti-vibe-coding rules |
| `docs/datasets.md` | Data sources, licences, evaluation experiments |
| `docs/final-prompt.md` | The staged delivery plan this repo follows |

Progress notes per stage live in `docs/stage-N.md`.

## Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, PostgreSQL + PostGIS, Celery + Redis, MinIO,
  Alembic, pytest + hypothesis.
- **Frontend:** Next.js 16 (App Router), TypeScript strict, Tailwind v4 driven by CSS variables
  from `docs/design.md`, TanStack Query, MapLibre GL JS (satellite + OSM basemaps).
- **Services:** TiTiler (COG tiles), pg_tileserv (vector tiles from PostGIS).
- **Everything:** Docker Compose.

## Architecture

```mermaid
flowchart LR
    subgraph client["Browser — Next.js 16 (web:3000)"]
        UI["Screens: overview · map · conflicts · sources · changes"]
        ML["MapLibre GL — Esri imagery / OSM, boundary, roads, layers"]
        Q["TanStack Query — every number comes from the API"]
    end

    subgraph api_layer["FastAPI (api:8000)"]
        R1["/sources — registry + licence, vintage, sha256"]
        R2["/sources/id/georef — CRS fit + QC + health"]
        R3["/matches/detect · /matches — feature matching"]
        R4["/conflicts — dispute queue"]
        R5["/healthz · /readyz"]
    end

    subgraph workers["Celery worker"]
        T["app.workers.tasks — ingest, detect, harmonize jobs"]
    end

    subgraph data["Data plane"]
        PG[("PostgreSQL + PostGIS<br/>storage SRID 32643")]
        MI[("MinIO — uploads, COGs")]
        RD[("Redis — queue")]
    end

    subgraph tiles["Tiles"]
        TT["TiTiler :8081 — raster tiles"]
        TS["pg_tileserv :7800 — vector tiles"]
    end

    POLICY["policies/naksha_default.yaml<br/>thresholds, weights, tolerances"]

    UI --> Q --> R1 & R2 & R3 & R4
    ML --> TT
    ML --> TS
    R2 & R3 & R4 --> PG
    R1 --> MI
    R1 & R3 -. job .-> RD --> T --> PG
    PG --> TS
    MI --> TT
    POLICY -. read by .-> R2 & R3 & T
```

## Workflow

```mermaid
flowchart TD
    A["1 — Register source<br/>GeoJSON / GeoTIFF / CSV + licence, vintage, sha256"] --> B
    B["2 — CRS fit<br/>declared CRS → storage EPSG:32643"] --> C
    C["3 — QC<br/>geometry validity, sliver area, duplicate vertices"] --> D
    D{"4 — Feature matching<br/>IoU across source pairs ≥ accept_threshold?"}
    D -->|"matched"| E["Auto-harmonized geometry"]
    D -->|"disjoint / crossing"| F["5 — Conflict queue<br/>overlap · boundary_crossing"]
    E --> G
    F --> G["6 — Reviewer decision<br/>select one source's geometry, evidence attached"]
    G --> H["7 — Append-only history<br/>every change recorded, never overwritten"]
    H --> I["8 — Map + OGC API Features<br/>reconciled layer over satellite basemap"]
```

## Running it

```bash
cp .env.example .env          # only needed if you want to override defaults
docker compose up --build -d
docker compose exec api alembic upgrade head
```

| Service | URL |
|---|---|
| Web | http://localhost:3000 |
| API | http://localhost:8000 |
| API reference | http://localhost:8000/docs |
| TiTiler | http://localhost:8081 |
| pg_tileserv | http://localhost:7800 |
| MinIO console | http://localhost:9001 |

Health: `GET /healthz` (liveness) and `GET /readyz` (PostGIS, Redis, MinIO and policy readiness).

## Working locally without Docker

```bash
# backend
cd backend
uv venv .venv --python 3.12
uv pip install -e ".[dev]"
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
.venv/Scripts/mypy app
.venv/Scripts/pytest

# web
cd web
npm ci
npm run lint && npm run typecheck && npm test && npm run build
```

## Rules that do not bend

1. Never fabricate data, metrics, users, testimonials or results. Synthetic data carries
   `is_synthetic = true` and a visible `SYNTHETIC` label.
2. Never invent geometry. Resolution selects one source's actual geometry or sends the case to a
   human. Boundaries are never averaged.
3. Automated repairs are bounded, logged and refusable.
4. No claim of legal title determination or official ULPIN issuance.
5. Owner personal data stays out of feature and OGC APIs and is reached only through a
   purpose-bound, audit-logged endpoint.
6. Confidence weights, thresholds and tolerances live in `policies/naksha_default.yaml`, not in
   code, and every one of them is a starting heuristic.
