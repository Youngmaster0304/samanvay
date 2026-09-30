# Stage 4 — Conflict queue, first slice (plan Stage 6)

Status: **complete slice, all gates green, live on real pilot data.**

This is the first slice of plan Stage 6: geometric conflict detection, the reviewer queue,
and append-only decisions. The policy engine (tiers, source hierarchy, auto-resolution)
is **not** built yet, so nothing here resolves anything automatically.

## What was built

| Piece | File | What it does |
| --- | --- | --- |
| Migration | `backend/alembic/versions/0004_conflicts.py` | `conflict` (unique per source pair + both feature ids, gist on evidence geometry) + `conflict_decision` (append-only) |
| Models | `backend/app/db/models.py` | `Conflict`, `ConflictDecision` |
| Detection | `backend/app/conflicts/service.py` | PostGIS pair join in the storage CRS; classification from the intersection geometry itself |
| API | `backend/app/api/conflicts.py` | `POST /conflicts/detect`, `GET /conflicts?state=&type=&limit=`, `POST /conflicts/{id}/decision` |
| Policy | `policies/naksha_default.yaml` | `conflicts:` block — `overlap_high_m2` 100, `overlap_medium_m2` 10, `crossing_high_m` 50, `crossing_medium_m` 5, `max_pairs` 5000 (all [P]) |
| Web client | `web/src/lib/conflicts.ts` | typed fetchers mirroring the API contract |
| Queue page | `web/src/app/(app)/queue/conflicts/page.tsx` | run detection between two loaded sources, filter the queue, decide with a required reason code |

## Detection rules (what counts as a disagreement)

- **polygon ∩ polygon with area** → `overlap`; severity from the intersection area.
- **line with part of itself outside the other feature** → `boundary_crossing`;
  severity from the measured length outside.
- **anything else is skipped on purpose**: roads meeting at a junction or parcels that
  merely share an edge are not evidence that two sources disagree.
- Re-running detection replaces only rows still in `queue`; decided rows are history and
  the unique pair key keeps re-runs idempotent.
- Disjoint pairs are not compared at all — that needs an AOI rule (later stage).

## Verification

Gates: backend `ruff check` · `ruff format --check` · `mypy app` · `pytest -q` → **80 passed**
(3 new API tests: overlap→severity→decide→409→re-detect history, boundary crossing with
measured length, and every refusal: `same_source`, `source_not_found`, `source_not_loaded`,
`conflict_not_found`).
Web: `npm run lint` · `npm run typecheck` · `npm test` (13) · `npm run build` (7 routes).

Live evidence (`scripts/conflicts_live_check.py` against the running stack):

```text
detect: pairs_examined=178  created=7
        by_type={boundary_crossing: 7}  by_severity={medium: 6, low: 1}
        policy=naksha_default v0.1.0 limits={crossing_medium_m: 5.0, crossing_high_m: 50.0, …}
queue:  405 x 0  15.2 m outside   medium
        374 x 0  20.5 m outside   medium
        16  x 0   3.7 m outside   low
        … 7 total, evidence geometry LineString per row
```

Both sources are real OSM extracts (494 roads vs the municipal boundary) — these are
genuine OSM-inconsistent road centrelines crossing the admin boundary, not synthetic rows.

Screenshot: `docs/stage-4-conflicts-1440.png` — the live queue at 1440 px with all seven
conflicts, severity words (never colour alone), measured metres, the policy sentence in
each reason, and per-row decision controls.

## Limitations (honest)

- No source hierarchy: every overlap waits for a reviewer, nothing auto-resolves.
- Reason codes are free text validated only for presence; the canonical code list arrives
  with the policy engine.
- Decisions record `actor` as sent (default `reviewer`) — there is no authentication yet.
- Evidence geometry is stored but the queue page shows measurements, not a map view; the
  map page renders the basemap layers only.
- Disjoint features and attribute-level disagreements are not detected.
