# design.md

Design system for **Samanvay** (working title), a harmonization workbench for urban land records.

Brief from you: **vibrant, and no generic blue or purple.** Your anti-vibe-coding checklist is built in (section 10). All contrast ratios below were computed with the WCAG formula on the exact hex values listed; re-check any value you change.

## 1. Concept

The product is a survey office desk with a screen on it. Three cues, each functional:

1. **Warm survey paper** as the ground colour, instead of pure white or dark-navy "tech" chrome.
2. **Marigold** as the one brand colour: high-saturation, warm, unmistakably not the default blue/purple AI palette, and it reads as a highlighter on a plan.
3. **Data colour first.** Each source layer, each status and each confidence grade has its own assigned colour. Most of the vibrance on screen comes from real data drawn over real drone imagery, not from decoration.

Feel: calm and exact around the edges, saturated where a decision is needed.

## 2. Vibrance rules (how it stays vibrant without turning noisy)

- Roughly 80–85% of the interface area is neutral paper and ink. Saturated colour is spent on: the primary action, the current selection, map data, status marks, and the confidence ramp.
- One brand hue. Do not add a second brand hue for variety.
- Imagery is content: the ORI carries the visual richness of the map screen.
- Saturated colours always sit against a neutral, never against each other (no orange-on-pink UI).
- No gradients in the UI chrome. The only gradient-like element is the sequential confidence ramp on the map, because it encodes data.

## 3. Colour system

### 3.1 Tokens

```css
:root {
  /* Neutrals: warm paper and ink */
  --paper-50:  #FBF8F1;  /* app background */
  --paper-100: #F4EEE1;  /* recessed regions, table stripes */
  --paper-200: #E8DFCC;  /* decorative dividers only */
  --surface:   #FFFDF7;  /* inputs, popovers, dialogs (warm, not pure white) */
  --stone-500: #857A67;  /* control borders (UI boundary, not text) */
  --stone-600: #6B6252;  /* secondary text */
  --ink-900:   #1A1712;  /* primary text */
  --ink-800:   #26221A;  /* dark surfaces */

  /* Brand: Marigold */
  --marigold-400: #FF8A3D;  /* primary on dark */
  --marigold-500: #F26A1B;  /* primary fill on light */
  --marigold-600: #B8480A;  /* pressed / small text on light (4.99:1) */
  --marigold-700: #933B08;  /* links and text on light (6.90:1) */
  --marigold-100: #FDE6D3;  /* tint for selected rows */

  /* Semantic */
  --paddy-600:  #1F7A3E;  --paddy-700: #17612F;  --paddy-400: #4CC077;   /* success, verified */
  --turmeric-500: #E7A400; --turmeric-700: #8A5F00; --turmeric-400: #FFC533; /* needs review */
  --chilli-600: #C4183C;  --chilli-700: #A01230;  --chilli-400: #FF6B85;   /* conflict, error */

  /* Data accent (map lines and one chart series only) */
  --rani-500: #D9327A;  --rani-600: #B92468;

  /* Roles */
  --text:        var(--ink-900);
  --text-muted:  var(--stone-600);
  --bg:          var(--paper-50);
  --border:      var(--paper-200);
  --border-ctl:  var(--stone-500);
  --primary:     var(--marigold-500);
  --on-primary:  var(--ink-900);      /* NOT white: see contrast table */
  --link:        var(--marigold-700);
  --focus:       var(--ink-900);      /* two-tone ring, see 6.3 */
}

:root[data-theme="night"] {   /* "Night survey" */
  --bg:         var(--ink-900);
  --surface:    var(--ink-800);
  --text:       #F3EDE0;
  --text-muted: #B5AA94;
  --border:     #3A3428;
  --border-ctl: #8F846F;
  --primary:    var(--marigold-400);
  --on-primary: var(--ink-900);
  --link:       var(--marigold-400);
  --focus:      #F3EDE0;
}
```
Do not use blue or purple anywhere: not for links, focus rings, selection, charts or map layers. Links are marigold-700 and underlined.

### 3.2 Verified contrast (WCAG 2.x ratios)

| Foreground on background | Ratio | Use |
|---|---|---|
| ink-900 on paper-50 | 16.85 | Body text |
| stone-600 on paper-50 | 5.67 | Secondary text |
| stone-600 on paper-100 | 5.20 | Secondary text on recessed areas |
| **ink-900 on marigold-500** | **5.83** | **Primary button label** |
| **white on marigold-500** | **3.06** | **Fails for normal text. Never use white on marigold-500.** |
| marigold-600 on paper-50 | 4.99 | Small text (AA, just) |
| marigold-700 on paper-50 | 6.90 | Links, preferred over 600 |
| white on marigold-600 | 5.29 | Pressed-state fill with white text |
| paddy-600 on paper-50 | 5.06 | Success text |
| white on paddy-600 | 5.37 | Success fill |
| chilli-600 on paper-50 | 5.59 | Error text |
| white on chilli-600 | 5.93 | Error fill |
| ink-900 on turmeric-500 | 8.26 | Warning fill with dark text |
| turmeric-700 on paper-50 | 5.33 | Warning text |
| rani-500 on paper-50 | 4.22 | **Below AA for normal text.** Map lines and large text only |
| white on rani-600 | 5.97 | Rani fill with text |
| stone-500 on paper-50 | 3.98 | Control borders (≥3:1 for UI components) |
| paper-200 on paper-50 | 1.25 | Decorative dividers only, never a control boundary |
| night: #F3EDE0 on ink-900 | 15.32 | Body text |
| night: #B5AA94 on ink-800 | 6.89 | Secondary text |
| night: marigold-400 on ink-800 | 6.75 | Primary/link |
| night: ink-900 on marigold-400 | 7.62 | Primary button label |
| night: paddy-400 on ink-800 | 6.87 | Success |
| night: chilli-400 on ink-800 | 5.80 | Error |
| night: turmeric-400 on ink-800 | 10.02 | Warning |

### 3.3 Map data palette

Each source kind has one colour, always drawn with a casing so it reads on both sunlit and shadowed imagery.

| Layer | Colour | Line style |
|---|---|---|
| Drone/AI-extracted | marigold-500 `#F26A1B` | solid, 2 px |
| Legacy cadastral | ink-900 `#1A1712` | solid, 1.5 px, light casing |
| Revenue records | rani-500 `#D9327A` | solid, 1.5 px |
| Municipal | lime `#8FBF00` | solid, 1.5 px |
| Utility | turmeric-500 `#E7A400` | dashed |
| GNSS/GT | ring: white outer, ink inner, marigold centre | point |
| Reconciled (canonical) | paddy-600 `#1F7A3E` | solid, 2 px |
| Conflict | chilli-600 `#C4183C` outline plus diagonal hatch | hatch, not fill alone |

Casing: 1.5 px extra width in `rgba(255,253,247,0.9)` under dark lines, and in `rgba(26,23,18,0.6)` under light lines. Test both against the real ORI, including shadows and bright roofs. Lime and rani are map-only.

### 3.4 Confidence ramp (Confidence display mode)

| Grade | Colour |
|---|---|
| A | `#1F7A3E` |
| B | `#8FAE2A` |
| C | `#E7A400` |
| D | `#E8791F` |
| E | `#C4183C` |

This ramp passes through red and green, so **colour alone is not enough**. Always pair with the grade letter (labels appear at high zoom, and in the inspector and tables). Provide a **colour-blind-safe alternative** ramp: single-hue marigold from light (low confidence) to dark (high confidence), selectable in the mode switch.

### 3.5 Status colours (chips and charts)

| Status | Fill | Text |
|---|---|---|
| auto_resolved | paddy-600 | white |
| accepted | paddy-700 | white |
| needs_review | turmeric-500 | ink-900 |
| dispute | chilli-600 | white |
| rejected | stone-600 | white |

Stacked status bar on Overview uses these fills with 1 px paper separators, and every segment is labelled with its count as text.

## 4. Typography

Two families, chosen for the product (a records tool with Hindi and English, dense tables, coordinates and IDs):

- **Source Serif 4** for headings: gives a gazette and ledger tone, avoids the popular sans-only look.
- **IBM Plex** superfamily for UI and data: Plex Sans (body, labels, buttons), **Plex Sans Devanagari** (Hindi text), **Plex Mono** (coordinates, IDs, code). One superfamily, three cuts, consistent metrics. Tabular numerals on in tables. Verify current availability of each cut on your font host before building.

Not used: Inter, Geist, Space Grotesk.

| Role | Font | Size / line | Weight |
|---|---|---|---|
| Display (About page title only) | Source Serif 4 | 40 / 46 | 600 |
| H1 | Source Serif 4 | 28 / 34 | 600 |
| H2 | Source Serif 4 | 22 / 28 | 600 |
| H3 | Plex Sans | 17 / 24 | 600 |
| Body | Plex Sans | 15 / 22 (16 / 24 on phones) | 400 |
| Small | Plex Sans | 13 / 18 | 400 |
| Label | Plex Sans | 12 / 16, letter-spacing +0.02em | 500 |
| Button | Plex Sans | 14 / 20 | 500 |
| Data and IDs | Plex Mono | 13 / 18 | 400 |

Rules: no more than one display heading per page; sentence case everywhere; uppercase only on status stamps (see 5.4). Body line length capped around 70 characters on reading pages. Devanagari runs use the Devanagari cut at the same size, with line-height raised by about 10%.

## 5. Components

### 5.1 Shape, spacing, elevation
- Spacing base 4 px: 4, 8, 12, 16, 24, 32, 48, 64.
- Radius: 4 px for inputs, buttons and chips; 6 px for panels; 8 px for dialogs. Nothing pill-shaped except toggles.
- Borders: 1 px `--border` for layout dividers, 1 px `--border-ctl` for input and control edges.
- Shadow: none on panels. One shadow for popovers and dialogs only: `0 4px 16px rgba(26,23,18,0.12)`.

### 5.2 Buttons
Four variants only.
- **Primary:** marigold fill, ink label, 40 px height (44 px on field screens). One per view region.
- **Secondary:** transparent, 1 px `--border-ctl`, ink label.
- **Quiet:** no border, ink label, underline on hover.
- **Destructive:** chilli-600 fill, white label; used only where data is discarded.
Hover: darken fill one step. Pressed: marigold-600 fill with white label (5.29:1). Disabled: stone tones with visible text. No hover lift, no scale.

### 5.3 Inputs
Visible labels above fields, 1 px stone-500 border, 4 px radius, helper text in stone-600, error text in chilli-600 preceded by an error mark and text ("Error: …"). Focus per 6.3.

### 5.4 Status stamps
Chips styled like record stamps: 2 px radius, 1 px border in their own colour, 12 px medium text, uppercase, letter-spacing +0.04em, always text (never colour only). Example: `NEEDS REVIEW`, `DISPUTE`, `AUTO-RESOLVED`. The `SYNTHETIC` badge uses a hatched turmeric background with ink text and appears wherever synthetic data appears.

### 5.5 Grade badge
Square-ish tile, 4 px radius: letter in Plex Mono bold, score below or beside it, filled with the ramp colour, text colour chosen by contrast (white on A, E; ink on C, D; check B). Include the letter even when the tile is small.

### 5.6 Panels and cards
Use panels only where content is a real group (inspector, evidence card, source detail). Do not wrap every row in a card. No coloured stripe on the left edge of anything. Use spacing and a 1 px divider to separate items.

### 5.7 Tables and queues
Dense: 36 px rows, 13 px text, tabular numerals, sticky header, zebra using paper-100 at low contrast, selected row uses marigold-100 with a 2 px marigold outline. Row focus ring per 6.3.

### 5.8 Evidence card
The most important component. Three geometry chips (same extent, same scale, one per candidate), a numbers table in Plex Mono, one-sentence recommendation, action buttons with visible key hints (`Enter`, `Shift+Enter`, `F`, `D`). Chips are labelled with source name and colour swatch.

### 5.9 Icons
Icons appear only where they carry meaning: navigation rail (always with a text label), map tools, status marks. One consistent outline set at 1.5 px stroke (choose one set and stay with it), plus a few custom map glyphs: GNSS point, swipe handle, offset arrow. No icon before every heading, no sparkle icons, no decorative arrows.

### 5.10 Brand mark
A wordmark set in Source Serif 4 with a small square mark: two 16 px squares, one outlined in ink and one filled marigold, offset by 3 px. It depicts two layers that have not yet been aligned. Static. No animation.

## 6. Interaction and motion

### 6.1 Motion rules
Motion communicates state or hierarchy, nothing else.
- Hover, focus and press: 120 ms ease-out on colour only.
- Panel open/close and sheet slide: 200 ms ease-out.
- Inspector content when the queue advances: 150 ms cross-fade.
- Progress: determinate bars for runs and uploads.
- Map: fly-to 600 ms for selection changes.
- **No** entrance animations on page load, no floating elements, no looping animation, no animated arrows, no hover lift.
- `prefers-reduced-motion: reduce` disables all of the above except progress; map fly-to becomes an instant jump.

### 6.2 Feedback
Actions confirm inline (chip changes, row leaves the queue, undo toast for 5 s). Errors say what failed and what to do next.

### 6.3 Focus
Two-tone focus ring: 2 px `--focus` outline with a 2 px offset in the surface colour, so it stays visible on paper, on dark panels and over imagery. Never remove focus outlines.

## 7. Layout principles

- **Workbench (≥1280 px):** three regions: layers (280 px), map (fluid), inspector (360 px), plus a queue strip. Panels dock; no floating overlapping panels.
- **768–1279 px:** map plus inspector as a slide-over; layers as a popover.
- **Below 768 px:** map full-bleed; layers, inspector and queue as bottom sheets with 44 px handles.
- **Overview:** varied composition, not a card grid. A wide stacked status bar across the top, a grade histogram and field progress side by side beneath it, then the last-run stage list as a table. Real numbers only.
- **About page:** editorial single column with real annotated screenshots of the workbench and one pipeline diagram using the actual stage names. No hero with three feature cards. No fake browser frames, no fake dashboards.
- **Field screens:** single column, one task in focus, 44–48 px targets, 16 px base text, high-contrast toggle (night theme), sunlight legibility tested outdoors.
- Breakpoints to test: 360, 768, 1024, 1440, 1920 px. No horizontal page overflow at any width; tables scroll inside their own container.

## 8. Content and voice

Plain, specific, and honest. Say what the tool did and what it did not.

| Instead of | Write |
|---|---|
| "Revolutionize your land records workflow" | "Matches parcels and buildings across departments' layers and shows where they disagree." |
| "AI-powered insights" | "The drone footprint is 7.2% smaller than the recorded area. Tolerance is 5%." |
| "Seamless integration" | "Reads GeoPackage, Shapefile, GeoJSON and COG. Writes OGC API Features." |
| "Confidence: high" | "Grade B (74). One source only, no second source agrees." |

Rules: no "unlock", "transform", "supercharge", "future of". No decorative em dashes in interface copy. No "it's not X, it's Y" constructions. Numbers always have units. Any AI-produced result is labelled as such and shows its evidence.

Hindi: provide translations for navigation, statuses and actions and have a fluent reader review them before the demo. Suggested starting terms (to review): विवाद (dispute), समीक्षा हेतु (for review), स्वीकृत (accepted), अस्वीकृत (rejected), भूखंड (plot), भवन (building). Keep technical terms readable rather than forcing awkward translations.

## 9. Trust and legal pages

Include real, plain pages: **About, Privacy Policy, Terms of Use, Contact.** Content requirements:
- State clearly that this is a prototype built for a hackathon and is not an official DoLR, Survey of India or NAKSHA system. No implied endorsement.
- Describe what data is handled, that owner information is access-controlled and each access is logged, retention, and how to request deletion.
- List data sources with licences (the licence tracker from `datasets.md`), and identify synthetic datasets.
- Contact: a real address you control.
- No testimonials, customer logos, user counts, awards or partnerships unless they are real and can be shown. If a section would need invented content, drop the section.

## 10. Anti-vibe-coding checklist, applied

Your 30 items, mapped to this system.

| # | Rule | How this design handles it |
|---|---|---|
| 1 | No harsh or excessive gradients | No gradients in chrome; only the data ramp |
| 2 | No random decorative icons | Icons only where they carry meaning, always with text |
| 3 | No white everywhere | Warm paper ground; surfaces are off-white `#FFFDF7` |
| 4 | No rainbow gradients | None |
| 5 | Limited shadows | One popover shadow only |
| 6 | No "3 feature cards" | Varied layouts, see section 7 |
| 7 | No emoji decoration | None |
| 8 | No glassmorphism | None; opaque surfaces |
| 9 | Few em dashes in copy | Rule in section 8 |
| 10 | Not default Inter/Geist/Space Grotesk | Source Serif 4 plus IBM Plex |
| 11 | No coloured left stripe on cards | Banned in 5.6 |
| 12 | No fake testimonials, users, metrics | Banned in 9 and in `front.md` |
| 13 | No bento overuse | No bento |
| 14 | No fake terminal or code windows | None |
| 15 | No "it's not X, it's Y" | Rule in section 8 |
| 16 | No checkmark bullets everywhere | Plain lists |
| 17 | No generic 3-tier pricing | No pricing |
| 18 | Mockups must show the real product | Screenshots from the running workbench |
| 19 | No squishy rounded UI | 4/6/8 px radii |
| 20 | No purple-and-black default | Marigold on warm paper; no blue or purple |
| 21 | No unnecessary skeleton loaders | Inline determinate progress |
| 22 | No glowing orbs | None |
| 23 | No dot-grid backgrounds | None (a real coordinate graticule appears only on the map) |
| 24 | No sparkle icons | None |
| 25 | No decorative animated arrows | Offset arrows appear only as data on the map |
| 26 | Terms of Service present | Section 9 |
| 27 | Privacy policy present | Section 9 |
| 28 | No hover animation on everything | Colour change only |
| 29 | No neon without reason | Saturation is used for data and decisions |
| 30 | No generic pastel template look | Warm, saturated, paper-based palette |

Do not overcorrect: the goal is intentional, not bare. Saturated colour, hatching, the confidence ramp and the night theme are all here because they do a job.

## 11. Accessibility summary
- Text contrast per section 3.2. Non-text contrast at least 3:1 for control boundaries.
- Never colour alone: grade letters, status text, hatch patterns.
- Visible two-tone focus on every interactive element.
- Targets at least 44 px on field screens, at least 32 px elsewhere with adequate spacing.
- Full keyboard operation; shortcuts documented in an overlay reachable with `?`.
- Reduced motion honoured.
- Map has a list equivalent.
- Semantic HTML, labelled controls, alt text on every image chip, `aria-live` for run progress.

## 12. Design review before merge
1. Could someone guess this came from a generic AI website prompt? If yes, simplify and replace with product-specific detail.
2. For each visual element: why does it exist, and does it help the user? If not, remove it.
3. Any blue, purple or pure-white background slipped in? Remove.
4. Any number on screen not returned by the backend? Remove.
5. Keyboard-only pass on the queue. Screen-reader pass on the evidence card.
6. Test the map colours over real imagery in bright and shadowed areas.
7. Check 360 px and 1920 px widths for overflow.
