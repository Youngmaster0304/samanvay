# Stage 2 — frontend workbench

Status: complete. Date: 2026-09-30.

## Scope and decisions

`docs/front.md` F0–F6 delivered as one Next.js 16 (App Router) + MapLibre GL app in `web/`.

Decisions taken while building (recorded so the next stage does not relitigate them):

- **Stack**: keep Next.js + MapLibre (FE-1a). The Vite/OpenLayers rewrite proposed in
  `docs/front.md` §FE-5 was dropped.
- **Design authority**: `docs/design.md` wins over the navy palette in the generated UI kit —
  marigold/paper, Source Serif 4 + IBM Plex, **no blue and no purple anywhere**. This is
  enforced by a test, not by review.
- **Basemap**: real OSM raster tiles with the ODbL attribution control (decision Q1=a). ORI
  imagery is not ingested, so nothing satellite-like is faked.
- **Data source**: pages read the live backend (`GET /sources`, `GET /readyz`). The MSW mock
  layer planned as Q2 was not installed — the backend existed first (Q3), and an honest
  empty state beats a mock the backend has to agree with.

## What was built

**Tokens and chrome (F0)** — `src/app/globals.css` carries the full token set: status fills
(auto-resolved / accepted / needs-review / dispute / rejected), the colour-blind-safe
`--grade-cb-1..5` ramp, `--space-*`, `--radius-*`, `--shadow-popover`, `--motion-*`, and
`--casing-light/dark`.

**Components** — `components/app-shell.tsx` (left rail on desktop, 6-tab bar on mobile,
`Wordmark`, `ThemeToggle` with a restored-before-paint dark theme), `components/map-canvas.tsx`
(dynamic MapLibre import, worker wiring, tilted initial view, layer visibility, fit-to-extent),
`components/api-status.tsx` (readiness table from `/readyz`, horizontally scrollable),
`components/badges.tsx` (`StatusChip`, `GradeBadge`, `SyntheticBadge`, `KindTag`),
`components/empty-state.tsx` (single honest action, no illustration, no skeleton).

**Screens** (`src/app/(app)/`)

| Route | Contents | Data |
| --- | --- | --- |
| `/` | overview: registry counts, "canonical features by status", service readiness, what this run did not check | live `GET /sources`, `GET /readyz` |
| `/sources` | registry table with search + kind filter, scrollable wide table | live `GET /sources` |
| `/map` | GIS workbench: layer sidebar (search, groups, eye toggles, legend) + dominant tilted map, toolbar with fit-extent | local layer state + MapLibre |
| `/queue/conflicts` | conflict queue | honest empty state (no endpoint yet) |
| `/changes` | change log | honest empty state (no endpoint yet) |
| `/about` | problem statement, scope, provenance rules | static |

**Static data** — `public/data/{sector22_boundary.geojson,sector22_roads.geojson,manifest.json}`
copied from `data/osm/`; the map draws only these two registered datasets.

**Layout of the map screen** follows the reference the prototype was shown: a thin icon rail,
a left layers panel with a search box and groups, and the map filling the rest of the
viewport, initially pitched (45°) so the pilot reads as a scene rather than a flat sheet.
Only real controls were built — layer visibility and fit-extent are wired; split compare,
offset arrows and the conflict hatch are named in the toolbar copy as Stage 4 rather than
drawn as dead buttons.

## The MapLibre worker failure (20-minute time-box)

**Symptom.** Every map render logged `Failed to fetch dynamically imported module:
http://localhost:3000/_next/...` and `Worker failed to load`, and the canvas stayed blank.

**Attempts in the agreed order.**

1. Console reading → the failing import was the *worker*, not the bundle: the request went to
   `/maplibre-gl-worker.mjs` and returned 404.
2. Static worker + `setWorkerUrl` → `maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs")`
   called before `new Map(...)`, with the file copied to `web/public/`. It still failed,
   because the worker itself does `import … from "./maplibre-gl-shared.mjs"`.
3. **Root cause**: the sibling module was missing — `maplibre-gl-worker.mjs` is not
   self-contained. Copying **both** `maplibre-gl-worker.mjs` and `maplibre-gl-shared.mjs`
   from `node_modules/maplibre-gl/dist/` into `web/public/` fixed it (no webpack path hack
   and no CSP change were needed).
4. Fallback (raster-only flag) was not required and was not built.

**Verification.** `GET /maplibre-gl-worker.mjs` → 200 `application/javascript` (19133 bytes);
a page-load probe logged no console errors; the map screenshot shows road centrelines and the
dashed boundary over OSM with the scale bar and ODbL attribution.

**Consequence to remember:** both files in `public/` must be re-copied whenever
`maplibre-gl` is upgraded (they are checked in next to `package-lock.json` for that reason).
`eslint.config.mjs` ignores `public/**` so the vendored files do not fail lint.

## Responsive check (and why a 360 px screenshot needs a harness)

The first 360 px screenshots looked cropped. A probe page measured the cause: with
`--window-size=360,740 --force-device-scale-factor=2`, headless Edge clamps its window and
reports `innerWidth: 483` (dpr 2) — the layout viewport is never 360, so content laid out at
483 px gets cropped to a 720 px image.

The working method is an iframe harness: a 400×820 page embedding the app in a
`360×740` iframe, so the app really lays out at 360 CSS px. Inside that frame the document
reports `clientWidth 345`, `scrollWidth 345`, and **zero overflowing elements**, and the
screenshots confirm it: all six bottom tabs fit, text wraps, and the sources table scrolls
inside its own panel. The harness file (`web/public/mobile-shot.html`) is removed after the
captures; recreate it from the snippet below when re-shooting.

```html
<iframe id="f" style="width:360px;height:740px;border:0"></iframe>
<script>
  var p = new URLSearchParams(location.search).get("page");
  if (p) document.getElementById("f").src = p;
</script>
```

## Screenshots

Captured from the running stack (`docker compose up -d`) with headless Edge:

```text
msedge --headless=new --disable-gpu --enable-unsafe-swiftshader --use-angle=swiftshader
  --user-data-dir=<fresh> --hide-scrollbars --force-device-scale-factor=<1|2>
  --window-size=<w,h> --virtual-time-budget=45000 --enable-logging=stderr
  --screenshot=<abs path> <url>
```

`--enable-unsafe-swiftshader` is required for WebGL in this environment, a fresh profile per
shot is required for `--window-size` to be honoured, and `--enable-logging` must be present or
the map canvas often comes back blank.

| File | Viewport | Shows |
| --- | --- | --- |
| `stage-2-overview-1440.png` | 1440×1100 | overview, live registry counts (2 sources), readiness all OK |
| `stage-2-sources-1440.png` | 1440×1100 | registry table with licence, CRS, checksum, sizes |
| `stage-2-map-1440.png` | 1440×1100 | workbench: layers sidebar + tilted map, roads/boundary rendered |
| `stage-2-conflicts-1440.png` | 1440×1100 | conflict queue, honest empty state |
| `stage-2-changes-1440.png` | 1440×1100 | change log, honest empty state |
| `stage-2-about-1440.png` | 1440×1100 | problem statement and provenance rules |
| `stage-2-overview-360.png` | 360×740 (iframe) | mobile shell, six-tab bar, wrapping hero |
| `stage-2-sources-360.png` | 360×740 (iframe) | mobile table inside its scroll container |
| `stage-2-map-360.png` | 360×740 (iframe) | mobile tabs (Layers/Map) + tilted map |
| `stage-2-conflicts-360.png` | 360×740 (iframe) | mobile empty state |

## Gates (2026-09-30)

| Gate | Result |
| --- | --- |
| `npm run lint` | clean |
| `npm run typecheck` | clean |
| `npm test` | 13 passed (2 files) |
| `npm run build` | 7 routes: `/`, `/about`, `/changes`, `/map`, `/queue/conflicts`, `/sources`, `/_not-found` |
| backend `ruff check` / `ruff format --check` / `mypy app` / `pytest` | pass / 47 files / 39 files / 54 passed |
| `docker compose build web` + `up -d web` | image `samanvay-web` built, container up |

## What was not built

- **No upload form.** Sources are registered through `POST /sources` or the ingest CLI
  (Stage 1). The overview's "Register a source" button links to the registry read view.
- **No conflict or change data.** Those two screens render `EmptyState` because no endpoint
  produces rows yet; no counts, charts or rows are invented. The "canonical features by
  status" panel on the overview states the same thing instead of drawing placeholder bars.
- **No ORI/tilt imagery, no swipe compare, no vector-tile overlays** — Stage 4/5 work.
- **MSW mock layer** (Q2) was dropped in favour of the live API; `NEXT_PUBLIC_USE_MOCKS` is
  not implemented.
- **Health/residual-RMSE columns** in the sources table read `—` until Stage 3 measures
  control points.

## Known limitations

- `NEXT_PUBLIC_API_BASE` defaults to `http://localhost:8000`; the browser calls it directly,
  so CORS (`WEB_ORIGIN`) must match the web origin.
- The basemap depends on `tile.openstreetmap.org` being reachable; without network the map
  shows the two GeoJSON layers over the paper background only.
- The mobile shell hides the left rail below 960 px and uses a bottom tab bar; the map screen
  switches between the Layers pane and the Map pane with tabs at that width.
- Vendored `public/maplibre-gl-*.mjs` files must be refreshed on a MapLibre upgrade.

## How to run it

```bash
docker compose up -d                 # full stack (api on :8000, web on :3000)
docker compose build web && docker compose up -d web
npm ci && npm run dev                # local web dev on :3000
npm run lint && npm run typecheck && npm test && npm run build
```
