# front.md

Frontend spec for **Samanvay** (working title). Pair with `design.md` (tokens, look and feel) and `backend.md` (API). This is a working tool for reviewers and surveyors first, and a presentable product second.

## 1. Who uses it and what they do

| Person | Device | Job | What speed means for them |
|---|---|---|---|
| **GIS reviewer** (state/ULB cell) | Desktop, large screen | Clear the conflict queue; accept, edit, defer, or send to field | Keyboard-driven, no page reloads, evidence visible without clicking around |
| **Supervisor** | Desktop | See progress, approve, export | Honest status counts, exports |
| **Field surveyor** | Phone in sunlight, patchy network | Go to assigned parcels, collect a GNSS point, close the task | Big targets, high contrast, works with weak connectivity |
| **Other department analyst** | Desktop or API | Pull reconciled layers | Clear metadata, licence, confidence, provenance |

Design for the reviewer first. The reviewer's queue is the product.

## 2. Stack

| Concern | Choice | Note |
|---|---|---|
| Framework | Next.js (App Router) with TypeScript, strict mode | Use the current stable release. |
| Map | MapLibre GL JS | Raster COG tiles from TiTiler, vector tiles from the tile server. |
| Swipe compare | MapLibre compare plugin or two synced maps | Verify plugin maintenance before committing. Fallback: single map with a CSS clip on a second map instance. |
| Server state | TanStack Query | Cache, retries, optimistic decisions. |
| UI state | Zustand (small) plus URL search params for map view and filters | Every view must be shareable by link. |
| Lists | TanStack Virtual | Queues can hold thousands of rows. |
| Styling | Tailwind with CSS variables from `design.md` tokens | No component-library default theme. |
| Primitives | Radix UI or React Aria for dialogs, menus, tabs, tooltips | Accessibility built in. Skin them with our tokens. |
| Charts | Small custom SVG components | No chart library for three chart types. |
| i18n | next-intl, English and Hindi | Keep strings in message files from day one. |
| Forms | React Hook Form plus Zod | Zod schemas shared with the API types. |
| Tests | Vitest, Testing Library, Playwright, axe | See section 10. |
| PWA | Service worker for the field queue only | Stretch. |

## 3. Information architecture

```
/                     Overview
/sources              Source registry
/sources/[id]         Source detail (health, residuals, licence)
/runs                 Runs list
/runs/[id]            Pipeline progress and results
/map                  Workbench (core screen)
/queue/conflicts      Conflict queue (list plus detail)
/queue/field          Field queue (mobile-first)
/changes              Change log
/evaluation           Measured results and their limits
/exports              Downloads and API endpoints
/about  /privacy  /terms  /contact
```

Top-level nav (desktop): Overview, Map, Conflicts, Field, Sources, Changes, Evaluation, Exports. On narrow screens: bottom tab bar with Map, Conflicts, Field, More.

## 4. Screens

### 4.1 Overview
Purpose: answer "where are we?" in five seconds.
- A stacked horizontal bar of canonical features by status: auto-resolved, accepted, needs review, dispute, rejected. Real counts only.
- Confidence distribution as a compact histogram by grade A to E.
- Field queue progress: open, assigned, surveyed, closed.
- Last run: stages, duration, policy version.
- A plain block titled "What this run did not check" listing known limits (for example: no legal title check; synthetic RoR used).
- Empty state: if no run exists, show the single action "Register a source" and a link to the data checklist. No fake charts.

### 4.2 Sources
Table: name, kind, authority, licence, vintage, CRS, feature count, sigma, `SYNTHETIC` badge where applicable, health (residual RMSE, coverage).
Detail page: CRS pipeline used, control-point residual table with blunder flags, extent on a small map, attribute crosswalk with the winning signal per column (editable), licence and attribution text.
Upload flow: file → detect CRS (require user confirmation if missing) → licence and synthetic flag (required fields) → register.

### 4.3 Run detail
Stage list with status, counts and timing: Ingest, Normalize, Extract, Match, Topology, Resolve, Score. Live progress by polling or SSE. Inline progress for stages of known length; no skeleton screens. Errors show stage, message, and a retry action. After completion: summary numbers plus links into the workbench pre-filtered.

### 4.4 Workbench (`/map`)

Layout on desktop:
```
┌───────────────┬──────────────────────────────────┬──────────────────────┐
│ Layers panel  │              Map                 │  Inspector           │
│ sources,      │  ORI base, vector overlays,      │  feature or conflict │
│ opacity,      │  swipe, offset arrows, hatching  │  evidence card       │
│ legend, mode  │                                  │                      │
├───────────────┴──────────────────────────────────┴──────────────────────┤
│ Queue strip: filters, counts, next/prev                                 │
└──────────────────────────────────────────────────────────────────────────┘
```
Mobile: full-screen map, layers and inspector as bottom sheets.

**Layers panel**
- One row per source with: colour swatch, name, kind, toggle, opacity slider, `SYNTHETIC` badge if set.
- Source colours come from `design.md` (data palette) and every vector layer gets a light casing so it reads over imagery.
- Display modes (segmented control): **Sources** (each layer in its colour), **Confidence** (canonical features coloured A to E), **Status**, **Change**.
- Legend always visible for the active mode.

**Map behaviours**
- Base: ORI via TiTiler; second base option: OSM-style neutral for context. No basemap whose licence we cannot show.
- **Swipe compare:** choose left and right layer (for example ORI vs ORI+legacy sheet overlay). Drag handle is keyboard-operable (arrow keys).
- **Offset arrows:** toggle to show displacement vectors between matched pairs, with the estimated systematic offset shown as one summary vector and its value in metres and bearing.
- **Conflict areas:** diagonal hatch fill plus outline so they never rely on colour alone.
- **GT points:** ring markers with accuracy shown on hover or focus.
- Scale bar (real, metric) and north arrow only if the map can rotate; graticule labels along the edge in the active CRS as a working reference.
- Coordinates readout on hover in WGS84 and the AOI's projected CRS. Click-to-copy.
- Selection sync: clicking a feature, a queue row or a URL param selects the same feature everywhere.

**Inspector, feature mode**
- Grade badge (letter plus number), and the six components as labelled bars with values.
- Chosen source and alternatives with their geometries.
- Recorded area vs geometry area, with the percentage difference and the tolerance in force.
- ULPIN field (linked/validated, never issued here), LGD codes, land-use class.
- History: decisions and re-runs, newest first.
- Owner details are **not** shown here. A separate "Owner record" button opens a purpose dialog (see 7).

**Inspector, conflict mode (the evidence card)**
- Header: conflict type and tier (T1 auto / T2 human) with the reason code.
- Two or three image chips of the same extent, one per candidate geometry, drawn over the ORI at the same scale.
- Numbers table: area A, area B, difference % vs tolerance %, positional distance, combined sigma, topology status, possession evidence yes/no.
- Recommendation: "Recommended: source X. Reason: …" in one sentence.
- Actions: **Accept recommended** (Enter), **Accept other** (Shift+Enter), **Edit geometry** (opens a vertex editor limited to snapping within tolerance), **Send to field** (F), **Defer** (D), **Comment**.
- After an action the card advances to the next conflict automatically; an **Undo** toast stays for a few seconds.

### 4.5 Conflict queue
Virtualized table of conflicts with sortable columns (type, tier, confidence, area difference, distance, age) and filters (type, ULB or ward, source pair). Row focus is the current item; the workbench inspector mirrors it. Bulk actions only for Tier-1 style groups the reviewer explicitly selects, with a confirmation that lists the count and the rule.

Keyboard: `J`/`K` next/previous, `Enter` accept recommended, `Shift+Enter` accept other, `F` send to field, `D` defer, `E` edit, `/` search, `?` shortcuts overlay.

### 4.6 Field queue
Mobile-first. One task at a time with an "up next" list.
- Task card: parcel ID or survey number, why it was chosen (short reason list), what to measure, distance and bearing.
- Map with the surveyor's position and the task geometry.
- **Submit GNSS point:** fields for fix type, accuracy (from the device if available), height, note, photo optional. Large buttons (at least 44 px), high-contrast mode for sunlight, works with poor connectivity by queuing submissions and showing queue state.
- Supervisor view (desktop): clusters on a map, assignment, status counts.
- Offline support is a stretch; if not built, show a clear "requires connection" state instead of failing silently.

### 4.7 Change log
List of detected changes by type (new, removed, moved, modified, split, merged, encroachment candidate), filterable by date and ULB, with map focus on click. Encroachment items are labelled "candidate for verification".

### 4.8 Evaluation
Table of experiments: name, AOI size, hardware, date, commit, metric values, and a **"What this does not show"** cell that is never empty. A short note distinguishes real-data results from controlled synthetic experiments.

### 4.9 Exports
Downloads (GeoJSON, GeoPackage, decision log CSV), the OGC API base URL with example requests, and a note that personal data is excluded.

### 4.10 About, Privacy, Terms, Contact
Real, plain-language pages. Must state: this is a prototype built for a hackathon, not an official DoLR or NAKSHA system; what data it handles; that owner data is access-controlled and logged; who to contact. No invented certifications or partnerships.

## 5. Component inventory

Build these once, reuse everywhere:
- `AppShell`, `NavRail`, `BottomTabs`
- `MapCanvas` (MapLibre wrapper), `LayerRow`, `ModeSwitch`, `Legend`, `SwipeControl`, `CoordReadout`
- `GradeBadge` (letter, number, pattern), `ComponentBars` (six score components)
- `StatusChip` (auto-resolved, accepted, needs review, dispute, rejected, open, assigned, surveyed, closed)
- `SyntheticBadge`
- `EvidenceCard`, `GeometryChip` (image crop with overlay), `NumbersTable`
- `QueueTable` (virtualized), `FilterBar`
- `StageList` (pipeline progress)
- `StackedStatusBar`, `GradeHistogram`
- `FieldTaskCard`, `GnssForm`
- `PurposeDialog` (owner lookup)
- `Toast` with undo, `ShortcutsOverlay`
- `EmptyState` (single action, no illustration)

Buttons: primary, secondary, quiet, destructive. Nothing else.

## 6. Data contracts (TypeScript)

Keep these in a shared package and generate from the API schema where possible.

```ts
export type Grade = 'A' | 'B' | 'C' | 'D' | 'E';
export type FeatureClass = 'parcel' | 'building' | 'road' | 'utility_line' | 'gnss_point';
export type FeatureStatus = 'auto_resolved' | 'needs_review' | 'dispute' | 'accepted' | 'rejected';

export interface ScoreComponents {
  pos: number; src: number; corr: number; topo: number; attr: number; ext: number; // 0..1
}

export interface CanonicalFeature {
  cid: string;
  featureClass: FeatureClass;
  geometry: GeoJSON.Geometry;            // WGS84 for the client
  status: FeatureStatus;
  confidence: number;                    // 0..100
  grade: Grade;
  components: ScoreComponents;
  capsApplied: string[];                 // e.g. ['open_conflict']
  chosenObs: string;
  alternatives: { obsId: string; sourceId: string; geometry: GeoJSON.Geometry }[];
  ulpin?: string;                        // linked or validated only
  lgd?: { village?: string; ulb?: string };
  areaRecorded?: { value: number; unit: string; sqm: number };
  areaGeometrySqm: number;
  areaDiffPct?: number;
}

export type ConflictType =
  | 'area_out_of_tolerance' | 'position' | 'overlap' | 'gap'
  | 'attribute' | 'split_merge' | 'encroachment_candidate';

export interface Conflict {
  conflictId: string;
  cid: string;
  type: ConflictType;
  tier: 1 | 2;
  state: 'open' | 'deferred' | 'sent_to_field' | 'resolved';
  evidence: {
    areaA?: number; areaB?: number; areaDiffPct?: number; tolerancePct?: number;
    distanceM?: number; combinedSigmaM?: number;
    topologyOk: boolean; possessionEvidence: boolean;
  };
  recommendedObs?: string;
  recommendationReason: string;          // one sentence
  reasonCode: string;                    // e.g. T2_AREA_OOT
}

export interface Decision {
  conflictId: string;
  action: 'accept_recommended' | 'accept_other' | 'edit' | 'defer' | 'send_to_field';
  chosenObs?: string;
  note?: string;
}

export interface Source {
  sourceId: string; name: string; kind: string; authority?: string;
  licence?: string; vintage?: string; isSynthetic: boolean; sigmaM?: number;
  crs: string; featureCount: number; residualRmseM?: number;
}

export interface FieldTask {
  taskId: string; cid: string; priority: number; reasons: string[];
  state: 'open' | 'assigned' | 'surveyed' | 'closed';
  location: GeoJSON.Point; distanceM?: number; bearingDeg?: number;
}
```

## 7. Personal data in the UI
- Owner names never appear in lists, tooltips, exports or the map.
- "Owner record" opens `PurposeDialog`: requires selecting a purpose from a fixed list and typing a short justification; the call is logged server-side. The dialog states this plainly.
- No owner data is cached in the browser beyond the open dialog.

## 8. States and feedback
- **Loading:** show inline progress where duration is known (uploads, runs). Do not add skeleton screens just to fill space.
- **Empty:** one sentence and one action.
- **Error:** what failed, what the user can do, a retry. Include a request ID users can copy.
- **Optimistic decisions:** apply locally, roll back with a message if the server rejects.
- **Long tasks:** SSE or polling with a visible stage and count.
- **Synthetic data:** any view that includes synthetic features shows a persistent `SYNTHETIC` marker.

## 9. Performance
- Vector overlays through vector tiles; never load all features as GeoJSON on the client.
- Limit simultaneous vector layers with labels; labels off by default beyond a zoom threshold.
- Debounce map-driven queries; cancel in-flight requests on view change.
- Virtualize queues and tables.
- Split the bundle: the map and editor load only on `/map` and `/queue/*`.
- Budget targets to verify in Lighthouse on a mid-range laptop and a mid-range phone **[P]**: interactive map under 3 s after data ready; queue navigation under 100 ms per key press.

## 10. Accessibility (non-negotiable)
- Every action reachable by keyboard; visible focus ring using the focus token in `design.md`.
- **Never encode meaning by colour alone.** Grades carry a letter; statuses carry text; conflict areas carry hatching; confidence ramp is paired with the grade letter.
- The map has a **list equivalent**: the queue table plus a feature table for the current viewport.
- Live regions announce run progress and decision outcomes politely.
- Text contrast per the verified ratios in `design.md`; touch targets at least 44 px on the field screens.
- `prefers-reduced-motion` disables non-essential transitions, including map fly-to (use jump).
- Forms have visible labels, described errors and no placeholder-only labels.
- Test with axe in CI and manually with a screen reader on the queue flow.

## 11. Internationalisation
- English and Hindi for navigation, statuses, buttons and errors from the start.
- Devanagari-capable font fallback (see `design.md`).
- Areas display in the recorded unit with the converted square-metre value beside it. Provide a unit switcher (sq.m, sq.ft, acre, guntha and others as data requires).
- Numerals: use Latin digits by default; format dates and numbers with `Intl`.

## 12. Testing
- Unit and component tests for `GradeBadge`, `EvidenceCard`, `StatusChip`, the decision reducer, and unit conversions.
- Playwright end-to-end: upload source → run → open workbench → accept 5 conflicts by keyboard → send one to field → export.
- Axe checks on every route.
- Visual regression on the evidence card and legend only (they carry meaning).

## 13. Build order
1. Shell, tokens, `MapCanvas` with ORI and vector tiles.
2. Layers panel and modes, feature inspector.
3. Conflict queue and evidence card, decisions with undo.
4. Sources and run pages.
5. Overview with real counts.
6. Field queue (mobile layout first).
7. Evaluation and exports.
8. About/Privacy/Terms/Contact pages.
9. Swipe compare, offset arrows, hatching polish.
10. i18n pass and accessibility pass.

## 14. Do not
- Show any number that the backend did not return.
- Use placeholder marketing copy, fake logos, fake testimonials or fake usage figures.
- Add decorative charts or animated hero sections.
- Depend on colour alone.
- Show owner data outside the purpose dialog.
