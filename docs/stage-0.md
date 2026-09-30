# Stage 0 — repo scaffold, compose stack, CI, health endpoints

Status: complete. Date: 2026-09-29.

## What was built

**Repository**

- `git init` at the repository root, `.gitignore` (venv, `node_modules`, `.next`, `__pycache__`,
  `.env`), `.dockerignore`, `.env.example`, `README.md`.
- The five specification files live in `docs/` (`research.md`, `backend.md`, `front.md`,
  `design.md`, `datasets.md`) plus `docs/final-prompt.md`, the staged delivery plan this repo
  follows.

**Docker Compose** — `docker-compose.yml`, eight services, all with `restart: unless-stopped`:

| Service | Image | Host port |
|---|---|---|
| `postgis` | `postgis/postgis:16-3.4` | 5432 |
| `redis` | `redis:7-alpine` | 6379 |
| `minio` | `bitnamilegacy/minio` | 9000, 9001 |
| `minio-init` | same image, creates the `samanvay` bucket | — |
| `api` | `backend/Dockerfile` | 8000 |
| `worker` | same image, Celery worker | — |
| `titiler` | `ghcr.io/developmentseed/titiler:latest` | 8081 |
| `tileserver` | `maptiler/tileserver-gl` (pg_tileserv) | 7800 |
| `web` | `web/Dockerfile` (Next.js standalone) | 3000 |

**Backend** — `backend/` (Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Celery)

- `app/main.py` — app factory, CORS from `WEB_ORIGIN`, policy loaded at startup (fails fast if the
  policy file is missing or unreadable).
- `app/api/health.py` — `GET /healthz` (liveness, reports `version`, `env`, `storage_srid`) and
  `GET /readyz` (503 until every dependency check passes: PostGIS, Redis, MinIO bucket, policy).
- `app/core/` — `config.py` (pydantic-settings), `policy.py` (`load_policy`/`get_policy`,
  accepts a `policy:` block wrapper, cached), `redis.py`, `objectstore.py` (MinIO client),
  `logging.py`.
- `app/db/session.py` — engine, session factory, `check_database()` readiness check. The
  `get_db` request dependency is deliberately not present yet; it lands with the first
  DB-backed endpoint in Stage 1.
- `app/workers/` — Celery app on Redis plus `app.workers.tasks.ping`.
- `alembic/` — `0001_enable_postgis.py`, the only migration. `downgrade()` is an explicit no-op:
  dropping `postgis` is impossible while the `tiger` sample data (installed by the image) depends
  on the extension.
- `policies/naksha_default.yaml` — every threshold, weight, tolerance and source sigma from
  `backend.md`, carrying the NAKSHA `[N]` values and the `[P]` priors that still need
  calibration. Nothing of that kind is hard-coded in the application.
- `tests/` — 4 tests: health, readiness contract, policy loading, Celery task registration.

**Frontend** — `web/` (Next.js 16 App Router, TypeScript strict, Tailwind v4, TanStack Query)

- `src/app/globals.css` — the design tokens from `docs/design.md` sections 3.1, 3.3 and 3.4 as
  CSS variables, mapped into Tailwind through `@theme inline`; type stacks for Source Serif 4 and
  IBM Plex Sans / Devanagari / Mono; `.btn--primary`, `.btn--secondary`, `.panel`, `.stamp`,
  `.data`, `.label`, `.divider`; the two-tone focus ring; the night theme; and the
  `prefers-reduced-motion` block. No blue and no purple appears anywhere in the file.
- `src/app/layout.tsx` — fonts via `next/font/google`, metadata, `providers.tsx`.
- `src/app/page.tsx` — the Stage 0 shell: wordmark, `h1`, the plain-language description, the
  single marigold primary button (label on `--ink-900`, never white) linking to `/docs`, and an
  explicit "What this prototype does not do" list.
- `src/components/api-status.tsx` — a live table that reads `GET /readyz` and prints the returned
  numbers only. Skeleton loaders are not used.
- `src/lib/api.ts` — `API_BASE`, `readyzUrl()`, `fetchReadiness()`.
- `tests/` — 9 tests: token presence for sections 3.1/3.3/3.4, dark primary labels, the
  no-blue-or-purple rule (every hex in the stylesheet is checked), night theme and reduced
  motion, focus ring, and the API URL builder.

**CI** — `.github/workflows/ci.yml`: backend job (`ruff check`, `ruff format --check`, `mypy`,
`pytest`), web job (`eslint`, `tsc --noEmit`, `vitest`, `next build`), and a compose job running
`docker compose config --quiet`.

## What was not built

Everything from Stage 1 onward: ingestion, source registry, CRS engine, control points, AI
footprint import, matching, topology repair, policy engine, confidence scoring, the platform and
OGC APIs, the map canvas, the conflict and field queues, the remaining pages, evaluation
scripts, and the accessibility/responsive pass. There is no dataset in the repository and no
geometry of any kind yet.

## Known limitations

- `downgrade()` on `0001` is a no-op, so `alembic downgrade base` does not return the database
  to a pre-extension state. Rebuilding from empty with `docker compose down -v` is the supported
  path back to zero.
- The `tileserver` and `worker` services carry no healthcheck; they are verified with
  `docker compose ps` and `celery inspect ping` instead.
- MinIO runs `bitnamilegacy/minio` because the official `minio/minio` image is no longer
  published on Docker Hub. The data volume path is `/bitnami/minio/data`.
- `next build` prerenders `/` as a static page; the readiness table fetches at runtime, so the
  table is empty at build time and populates in the browser.
- The page-level `axe` run required by the master prompt is deferred to Stage 14; CI currently
  runs lint, type-check, unit tests and build only.
- The Compose `config` CI job validates the file but does not start the stack.

## How to run it

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
```

Local checks without Docker:

```bash
cd backend
uv venv .venv --python 3.12
uv pip install -e ".[dev]"
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
.venv/Scripts/mypy app
.venv/Scripts/pytest

cd ../web
npm ci
npm run lint && npm run typecheck && npm test && npm run build
```

## Evidence

**Checks (all exit 0)**

```
ruff check .            All checks passed!
ruff format --check .   19 files already formatted
mypy app                Success: no issues found in 16 source files
pytest                  4 passed, 1 warning in 0.84s
npm run lint            exit=0
npm run typecheck       exit=0
npm test                Test Files 2 passed (2), Tests 9 passed (9)
npm run build           ✓ Generating static pages (3/3), exit=0
docker compose config --quiet   exit=0
```

**Stack**

```
NAME                    STATUS                    PORTS
samanvay-api-1          Up (healthy)              0.0.0.0:8000->8000/tcp
samanvay-minio-1        Up (healthy)              0.0.0.0:9000-9001->9000-9001/tcp
samanvay-postgis-1      Up (healthy)              0.0.0.0:5432->5432/tcp
samanvay-redis-1        Up (healthy)              0.0.0.0:6379->6379/tcp
samanvay-tileserver-1   Up                        0.0.0.0:7800->7800/tcp
samanvay-titiler-1      Up (healthy)              0.0.0.0:8081->80/tcp
samanvay-web-1          Up (healthy)              0.0.0.0:3000->3000/tcp
samanvay-worker-1       Up
```

**Migrations from scratch** — after `docker compose down -v`, the volume is empty
(`alembic_version` table count `0`), then:

```
alembic upgrade head   Running upgrade  -> 0001, enable postgis extension
SELECT version_num      alembic_version=0001
SELECT extversion       postgis=3.4.3
alembic downgrade base  Running downgrade 0001 -> , enable postgis extension
alembic upgrade head    Running upgrade  -> 0001, enable postgis extension
alembic current         0001 (head)
```

**Health endpoints**

```
GET /healthz
{"service":"samanvay-api","status":"ok","version":"0.1.0","env":"dev","storage_srid":32646}

GET /readyz
{"service":"samanvay-api","status":"ready","version":"0.1.0","checks":{
  "database":{"ok":true,"postgis_version":"3.4 USE_GEOS=1 USE_PROJ=1 USE_STATS=1"},
  "redis":{"ok":true},
  "object_store":{"ok":true,"bucket":"samanvay"},
  "policy":{"ok":true,"name":"naksha_default","version":"0.1.0",
            "path":"/app/policies/naksha_default.yaml"}}}
```

**Worker**

```
celery inspect ping   ->  celery@0f5309f090b2: OK   pong   1 node online.
```

**Web shell** — `GET http://localhost:3000` returns `200`, 17095 bytes. Screenshot at
1440×1100: `docs/stage-0-web-shell.png`. It shows the warm `#fbf8f1` paper background, Source
Serif 4 headings, the `PROTOTYPE` stamp, the single marigold `#f26a1b` primary button with a
dark label reading "Open API reference", and the Service readiness table populated from
`/readyz` with the backend's own numbers (PostGIS 3.4, bucket `samanvay`,
`naksha_default v0.1.0`).
