# Stage 1 — ingest and source registry

Status: complete. Date: 2026-09-29 (evidence re-run 2026-09-30).

## Plan (concrete actions)

1. Dependencies: add `geopandas` (brings pyogrio, shapely, pyproj, pandas) and `rasterio` to
   `backend/pyproject.toml`; install into the local venv and into the api/worker images.
2. `app/domain/sources.py` — `SourceKind` and `SourceFormat` enums, format rules per kind.
3. `app/ingest/` package:
   - `errors.py` domain errors with a stable `code` and HTTP status,
   - `gdal_guard.py` process-wide GDAL limits (no sidecar scanning, HTTP timeouts, 64 MB
     cache, `SHAPE_RESTORE_SHX` so a bare `.shp` is readable),
   - `checksums.py` streaming SHA-256,
   - `csv_columns.py` coordinate-column detection for GNSS CSVs,
   - `detect.py` extension + magic-byte format detection,
   - `crs.py` CRS normalisation and the resolve rules (file → declared → implicit → reject),
   - `store.py` `ObjectStore` protocol with a MinIO implementation,
   - `service.py` the ingest pipeline: spool with size limit → hash → idempotency → detect →
     unpack archive → inspect → resolve CRS → validate kind/format → store → insert,
   - `cli.py` `python -m app.ingest.cli` for scripts and containers,
   - `connectors/` `cog`, `geojson`, `gpkg`, `shp`, `csv_gnss`, `csv_ror`.
4. `app/db/models.py` — `SourceRegistry` mapping; migration `0002_source_registry`.
5. `app/api/sources.py` — `POST /v1/sources` (multipart), `GET /v1/sources`,
   `GET /v1/sources/{id}`; register in `app/main.py`.
6. Settings: `MAX_UPLOAD_BYTES`, `COG_CONVERT_MAX_BYTES` (operational limits, environment
   config, not policy thresholds).
7. Tests: test-database fixture that provisions a fresh `samanvay_test` database and runs the
   migrations on it, in-memory object store, fixtures generated at test time with
   geopandas/rasterio (nothing written to git).
8. CI: Postgres service, `alembic upgrade head` (proves migrations from scratch on every push),
   `DATABASE_URL` for the job.
9. Run every quality gate, rebuild the stack, ingest real files through the API, capture output.
10. Write the "what was built / not built / limitations / evidence" sections below.

## Scope boundary

`backend.md` §1 draws Ingest's output as *object store + source_registry*. Feature geometry is
loaded into `source_feature` downstream, once the Stage 2 CRS engine can put it in the storage
CRS, so this stage stores the original bytes and records what the file actually contains
(feature count, coverage, schema, raster dimensions) as read back from the file.

## What was built

Backend only (`backend/`), 46 Python files:

- **Dependencies**: `geopandas` (pulls pyogrio, shapely, pyproj, pandas) and `rasterio` in
  `pyproject.toml`, installed into the local venv and into the api/worker images;
  `libexpat1` added to the Dockerfile for GDAL's XML parsing.
- **Domain** `app/domain/sources.py` — `SourceKind`, `SourceFormat` enums and the format rules
  allowed per kind.
- **Ingest package** `app/ingest/`:
  - `errors.py` domain errors with a stable `code` and HTTP status,
  - `gdal_guard.py` process-wide GDAL limits (no sidecar scanning, HTTP timeouts, 64 MB
    cache, `SHAPE_RESTORE_SHX` so a bare `.shp` is readable),
  - `checksums.py` streaming SHA-256, `detect.py` extension + magic-byte format detection,
  - `csv_columns.py` coordinate-column detection for GNSS CSVs,
  - `crs.py` normalisation and the resolve order file → declared → implicit → reject,
  - `archive.py` bounded zip unpacking (entry count and unpacked size),
  - `store.py` `ObjectStore` protocol with a MinIO implementation,
  - `service.py` the pipeline: spool with size limit → hash → idempotency → detect → unpack →
    inspect → resolve CRS → validate kind/format → store → insert,
  - `cli.py` (`python -m app.ingest.cli`), and connectors
    `cog`, `geojson`, `gpkg`, `shp`, `csv_gnss`, `csv_ror`.
- **Registry** `app/db/models.py` `SourceRegistry` mapping; migrations
  `0001_enable_postgis.py`, `0002_source_registry.py`. Unique keys: `source_id`,
  `client_key`, and `(sha256, kind)`.
- **API** `app/api/sources.py` — `POST /sources` (multipart), `GET /sources`,
  `GET /sources/{source_id}`; health in `app/api/health.py` (`/healthz`, `/readyz`, which
  reports `storage_srid`). Registered in `app/main.py` with CORS for `WEB_ORIGIN`.
- **Settings** `app/core/config.py` — `STORAGE_SRID` (default 32643), `MAX_UPLOAD_BYTES`
  (512 MiB), `MAX_ARCHIVE_ENTRIES` (4096), `MAX_ARCHIVE_BYTES` (2 GiB). Operational limits
  only; quality thresholds stay in `policies/naksha_default.yaml`.
- **Tests** `backend/tests/` — `test_detect`, `test_crs`, `test_archive`, `test_connectors`,
  `test_sources_api`, `test_health`; `conftest.py` provisions a fresh `samanvay_test`
  database, runs the migrations on it, uses an in-memory object store and generates fixtures
  with geopandas/rasterio at test time (nothing written to git).
- **CI** `.github/workflows/ci.yml` — backend job with a `postgis/postgis:16-3.4` service,
  `ruff check`, `ruff format --check`, `mypy app`, `alembic upgrade head`, `pytest`; web job
  `npm ci` + lint/typecheck/test; a compose config job.

## What was not built

- **Feature loading stops here.** Ingested geometry is not written to a `source_feature`
  table (the table does not exist yet); reprojection into the storage CRS and feature loading
  belong to the Stage 2 CRS engine, per the scope boundary above.
- **No web upload form.** Registration runs through `POST /sources` or the CLI; the Stage 2 UI
  only reads the registry.
- **No tiling of registered data.** `titiler` and `tileserver` services exist in compose but
  nothing feeds them yet (Stage 4).
- **No raster evidence run.** The COG connector and its tests exist, but the live proof below
  covers GeoJSON only; no GeoTIFF was ingested through the running API.
- **No OGCAPI Features / discovery endpoints**, no search beyond kind and client key, no
  delete or update API (the registry is append-only in this stage).

## Known limitations

- `crs_used` records what the file actually carried (`EPSG:4326` for OSM exports); nothing is
  reprojected to `STORAGE_SRID` at ingest time — that is deliberate and documented above.
- `licence`, `authority` and `vintage` are recorded exactly as supplied by the caller. They
  are not verified against the upstream publisher.
- Idempotency is per `(sha256, kind)`: the same bytes registered under a second kind create a
  second row; the same `client_key` is rejected by a unique index.
- Archive bounds (4096 members, 2 GiB unpacked) and the 512 MiB upload cap are refusal
  limits, not safety guarantees; there is no malware scanning.
- `feature_count`, `coverage`, `attributes` and `geometry_types` are read back from the file
  with GDAL and can be wrong if the file lies about its own content.

## How to run it

```bash
docker compose up -d                      # postgis, redis, minio, api, worker, web, tiles
docker compose exec api alembic upgrade head
docker compose exec api python -m app.ingest.cli /data/osm/sector22_boundary.geojson \
  --name "OSM Sector 22 municipal boundary" --kind municipal \
  --licence ODbL-1.0 --authority "OpenStreetMap contributors" \
  --vintage 2026-09-30 --url https://www.openstreetmap.org/relation/7894503
curl http://localhost:8000/sources        # list
curl http://localhost:8000/sources/{id}   # one row
```

Upload over HTTP instead of the CLI:

```bash
curl -F "file=@sector22_roads.geojson" -F "name=OSM Sector 22 roads" \
  -F "kind=municipal" -F "licence=ODbL-1.0" -F "authority=OpenStreetMap contributors" \
  http://localhost:8000/sources
```

Local gates (run from `backend/`):

```bash
uv pip install --python .venv/Scripts/python.exe ".[dev]"
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m mypy app
.venv/Scripts/python.exe -m pytest -q
docker compose config --quiet
```

## Evidence

Re-run on 2026-09-30 against the live stack (`docker compose up -d`).

**Gates**

| Gate | Result |
| --- | --- |
| `ruff check .` | All checks passed! |
| `ruff format --check .` | 47 files already formatted |
| `mypy app` | Success: no issues found in 39 source files |
| `pytest -q` | 54 passed (exit 0) |
| `docker compose config --quiet` | exit 0 |
| CI | backend (postgis service + migrate + pytest), web (lint/typecheck/test), compose jobs defined in `.github/workflows/ci.yml` |

**Ingest through the CLI, then re-ingest of the same bytes**

```
$ python -m app.ingest.cli ../data/osm/sector22_boundary.geojson ...
{
  "source_id": "4276295e-4090-41cb-9a97-c1ab8e382aac",
  "name": "OSM Sector 22 municipal boundary",
  "sha256": "122a8ca1f48ac20927b94899dec5387f5c0c57069ed7e59972c91c0f5584bad3",
  "object_key": "sources/12/122a8ca1f48ac20927b94899dec5387f5c0c57069ed7e59972c91c0f5584bad3/sector22_boundary.geojson",
  "crs": "EPSG:4326", "crs_source": "file",
  "coverage": [76.7629635, 30.7263491, 76.7797155, 30.7397398],
  "feature_count": 1, "is_synthetic": false,
  "reused": true, "reuse_reason": "same_sha256"
}
```

**Registry rows** (`select … from source_registry`)

```
 source_id                               | name                             | format  | crs_used  | feature_count | size_bytes | object_key
 4276295e-4090-41cb-9a97-c1ab8e382aac    | OSM Sector 22 municipal boundary | geojson | EPSG:4326 |            1 |        909 | sources/12/122a8…/sector22_boundary.geojson
 d56a3fdf-31f8-4a2b-83c7-deac8441c431    | OSM Sector 22 roads              | geojson | EPSG:4326 |          494 |     150260 | sources/1a/1a95ee84…/sector22_roads.geojson
```

**API**

- `GET /openapi.json` → `['/healthz', '/readyz', '/sources', '/sources/{source_id}']`
- `GET /sources` → `total: 2`, newest first; both rows carry `licence ODbL-1.0`,
  `authority OpenStreetMap contributors`, `vintage 2026-09-30`, `crs EPSG:4326`,
  checksum `1a95ee84…f396` (roads) and `122a8ca1…bad3` (boundary).
- `GET /readyz` → `status: ready`, `database.postgis_version 3.4 USE_GEOS=1 USE_PROJ=1
  USE_STATS=1`, `redis ok`, `object_store bucket "samanvay"`,
  `policy naksha_default v0.1.0`.

**Frontend consumption**: `docs/stage-2-*.png` show these two rows and the readiness
checks rendered by the Stage 2 UI.
