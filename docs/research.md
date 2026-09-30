# SIH 2026, PS 26013: research brief

**Problem:** Automated Integration and Intelligent Harmonization of Multi-source Geospatial Data for Urban Land Record Management
**Owner:** Ministry of Rural Development, Department of Land Resources (DoLR). Category: Software. Theme: Smart Automation.
**Research date:** 29 Sep 2026

Tagging used below: **[V]** = verified from a source I opened this session (link in Sources). **[B]** = background knowledge, verify before you put it in a slide. **[A]** = my assumption or recommendation.

---

## 1. What we are actually building (one paragraph)

A harmonization engine and reviewer workbench that takes the layers NAKSHA teams already have (drone ORI, DSM/DTM, AI-extracted footprints, legacy cadastral maps, revenue RoR, municipal GIS, utilities, GNSS ground truth), aligns them to one coordinate frame, matches features across layers, flags where they disagree, resolves what can be resolved by explicit rules and evidence, scores every output feature, and hands the remaining conflicts to a human with the evidence attached. The output is one reconciled parcel and building layer that other departments can pull through standard APIs. **[A]**

The important framing: this is **adjudication of disagreeing sources**, not ETL. ETL moves data; here the sources contradict each other and someone has to decide, defensibly, and record why.

## 2. The real workflow we are plugging into

NAKSHA runs in three sequential "maps" **[V: Frontiers paper, NAKSHA booklet]**:

| Stage | What happens | Who |
|---|---|---|
| MAP-1 aerial survey | Drone or aircraft survey at about 5 cm GSD. Outputs: ORI, DSM, DTM, 2D/3D feature extraction. QA/QC by Survey of India. | SoI plus third-party UAV vendors, loaded to the MPSEDC portal |
| MAP-2 field survey | GNSS rover ground truthing of every parcel with ORI as basemap. Ownership documents verified. Draft published for claims and objections. | States/UTs, ULB field teams |
| MAP-3 final publication | Claims and grievances resolved. Final urban property cards (UrPro) issued. | States/UTs with MPSEDC and NICSI |

Our platform sits **between MAP-1 outputs and MAP-2/3 decisions**: it prepares the draft parcel layer, tells surveyors where to go first, and cleans what comes back.

### The reconciliation protocol NAKSHA already describes **[V]**

The Frontiers paper (co-authored by a DoLR official) describes a three-tier way of reconciling drone-derived parcel boundaries with legacy cadastral records, where deviations of up to 5% occur:

1. Digitize and georeference legacy maps using high-accuracy GCPs and spline or polynomial rubber-sheeting.
2. Apply a 5% parcel-area tolerance. If a parcel is inside tolerance and matches current possession on the ground, the drone-derived boundary becomes the authoritative geometry.
3. Parcels outside tolerance, or with topology conflicts (overlaps, gaps), are automatically flagged as Dispute/Anomaly cases, verified by GNSS-assisted mobile GIS survey, then jointly validated with owners and revenue officials.

**This is the single most useful finding.** Our conflict-resolution engine should implement this protocol as its default policy, with the tolerance configurable. That makes the demo speak the department's own language. Confirm the exact numbers against the NAKSHA SOP before presenting them as official rules. **[A]**

## 3. Where the pain is (evidence for the problem statement)

- **Ground truthing is the bottleneck.** As of 31 Mar 2026, 44 pilot ULBs had reached 100% ground truthing, 16 were above 60%, and 55 were below 60% **[V]**. Aerial data is far ahead: ORI and DSM were submitted and QA'd for 116 to 118 ULBs **[V]**. So imagery outruns field verification. A tool that ranks where field teams should go first has direct value.
- **Institutional fragmentation.** One parcel can be governed by four bodies: revenue (RoR), municipality (property tax), development authority (land use and permissions), sub-registrar (deeds), historically without shared identifiers **[V]**. The paper proposes a unified property ID and interoperable Web-GIS as the fix.
- **Legacy maps are old.** Existing cadastral maps are decades out of date where they exist, and miss vertical growth and subdivisions **[V]**.
- **Manpower.** Acute shortage of GIS and remote sensing staff at ULB level. The paper explicitly lists GeoAI feature extraction as a way to cut manual load **[V]**.
- **Update problem.** Rwanda's experience: 87% of rural transactions were still informal five years after first registration, so a cadastre goes stale unless updating is cheap **[V, via Frontiers]**. Our change detection is the "cheap updating" story.
- **3D and tenure complexity.** Apartment complexes, informal settlements, peri-urban fringe. 3D property law does not exist in most states yet **[V]**. We should show height (nDSM) but not claim legal 3D titles.

## 4. Programme facts you will need (all verified)

- NAKSHA is under DILRMP, implemented by DoLR. Pilot: about 150 ULBs (152 in launch coverage) across 26 states and 3 UTs, ₹194 crore, 100% centrally funded, launched 18 Feb 2025 at Raisen, MP **[V]**. Figures vary slightly across sources (150 vs 152 ULBs; 25 vs 26 states). Use "about 150" unless you cite a specific document.
- Scale-up target: all 4,912 ULBs, with a first phase of 1,000 ULBs **[V, booklet]**.
- Three aerial technologies: 2D nadir, 3D oblique (5 cameras), oblique plus LiDAR. Counts differ between the paper's text (80/47/25 ULBs) and its own figure (55/43/22) **[V]**. Avoid quoting the split.
- Roles: Survey of India (technical partner, aerial survey, feature extraction, QA/QC), MPSEDC (web-GIS platform), NICSI (cloud, storage, DB management, security audit), CoEs (training), States/UTs (field survey, GNSS rovers, record integration) **[V]**.
- **DILRMP 3.0** operational guidelines launched 10 Sep 2026: ₹565.50 crore, 2026 to 2031, 100% central funding, phased and performance-linked **[V]**. It introduces a **Land Stack**: georeferenced cadastral maps, RoR, property registrations and court matters linked through GIS interfaces and APIs. Each State builds its own Land Stack; these form a **federated** National Land Stack where states keep ownership and control of their data **[V]**.
- **ULPIN / Bhu-Aadhaar:** 14-digit alphanumeric parcel ID generated from parcel vertex coordinates, aligned with ECCMA and OGC standards **[V, DoLR page]**. It identifies a parcel; it is not proof of title **[V]**. Do not claim our platform issues official ULPINs. Show a ULPIN field that we link and validate.
- Earlier DILRMP phases digitized 99.90% of RoRs and 97% of cadastral maps, with 99% of Sub-Registrar Offices computerized **[V]**. So rural cadastral data is largely digital; urban is where the gap is.
- Survey of India CORS: 1,047 permanent stations reported, and SoI is working with DoLR to add temporary and permanent stations in ULBs under NAKSHA **[V]**. Real-time correction accuracy of about 3 cm is quoted in secondary sources **[V, secondary]**.

**Why DILRMP 3.0 matters for the pitch:** it launched 19 days ago. The direction of travel is "from isolated digitization to full system integration" **[V]**. Our platform is a concrete answer to that sentence. Use the Land Stack framing: we do not replace state systems, we sit beside them and expose federated APIs.

## 5. Competitor and prior-art scan

**Important:** public repositories for this exact problem statement already exist. Judges may have seen similar work. Do not copy; differentiate.

| Repo | What it claims (self-reported, unverified by me) | Read |
|---|---|---|
| `sid-vj/GeovaX` | Full platform named for PS 26013. Real Indian government data (Chennai, 22 km²), 107,262 harmonised features, Dempster-Shafer conflict fusion, claims-not-records data model, ULPIN minting, Merkle-anchored provenance ledger, 81 tests, honest limits documented. | The strongest one I found. Backend-heavy, evidence-theory framing. |
| `RUSHIT305/cadastral-ai-` | "CadastreAI": parcel boundary segmentation, footprints, topology validation, risk-based GT queue, web workbench, ULPIN, RoR export. | Broad feature list, marketing-style README. |
| `Darshitvarshney/ps02` | "NAKSHA GeoAI" platform mapping every dataset in the PS. | Thin public detail. |

I did not run any of their code. Treat their numbers as claims.

**What they tell us:**
1. Real data beats synthetic in a demo. GeovaX makes that its headline.
2. Confidence scoring, topology repair and a review queue are table stakes.
3. Everyone lists the same modules. The winner is the team whose demo **feels like the department's actual workflow** and whose numbers are honest.

**Industry tools (background) [B]:** Esri ArcGIS Parcel Fabric, FME, 1Spatial rules-based validation, QGIS with PostGIS, and open conflation tools such as Hootenanny. These are why "we use GIS" is not a differentiator. Our angle is the NAKSHA-specific policy plus the field-queue loop.

## 6. Technical research by sub-problem

### 6.1 AI feature extraction (building footprints from ORI)
- Segmentation-then-vectorize is the standard pipeline. Raster masks need regularization before they are database-ready: merged buildings, fragments, warped edges and false positives show up in practice **[V, GeoAwesome summary of a UAV study]**.
- A study on 15 cm UAV orthophotos in Bangladesh compared U-Net (ResNet-34) and a LoRA-adapted SAM, then added a polygon-level quality classifier using 24 features **[V]**. Takeaway: **a QC layer on top of the extractor is publishable and useful.** We can copy the idea in a lighter form: score every AI polygon before it enters matching.
- SAM-based extraction on 5 cm true orthophotos reported F1 of about 94 to 95% and IoU of about 88 to 90% in low and medium density areas, with a small accuracy drop after regularization **[V, thesis abstract]**. Dense areas and vegetation occlusion are weaker. Expect the same in Indian dense cores.
- Off-nadir (oblique) footprint extraction is its own research area (PolyFootNet on SAM) **[V]**. For hackathon scope, use nadir ORI only.
- **[A]** Do not train a big model in the hackathon window. Use a pretrained or lightly fine-tuned model, precompute on the demo AOI, and put effort into QC, matching and conflict logic.

### 6.2 Parcel boundary extraction
- Cadastral boundary delineation from UAV imagery works where boundaries are physically visible (walls, fences, hedges, road edges). One study on 0.02 to 0.25 m imagery from Kenya, Rwanda and Ethiopia reported 71% accuracy for a CNN boundary classifier and, in rural scenes, 38% less time and 80% fewer clicks than manual delineation **[V]**. Performance depends on visible boundaries **[V]**.
- Implication: in Indian urban areas, many parcel boundaries are invisible (shared walls, interior lines). **Do not promise automatic parcel extraction.** Frame AI as proposing visible-boundary candidates, and the legacy cadastral as the parcel topology source that gets aligned to the ORI.

### 6.3 Georeferencing and coordinate transformation
- Legacy sheets need control-point-based rubber-sheeting (spline/polynomial) **[V, NAKSHA protocol]**.
- **[B]** Older Indian maps use Everest-based datums and local zone projections; PROJ supports transformations but grid availability varies. Build the engine on `pyproj`, expose the source and target CRS explicitly, and log the transformation pipeline and residuals per layer. Verify EPSG codes for legacy datums before use.
- **[A]** Estimate a **systematic offset** between layers first (median displacement of confidently matched pairs), apply it, then re-match. GeovaX reports finding a 1.51 m systematic offset between two departments' layers; the idea is sound and cheap.

### 6.4 Spatial matching (conflation)
Pipeline we should use **[A, standard practice]**:
1. **Blocking** with an R-tree or grid index so you only compare nearby candidates (removes over 99% of pairs).
2. **Pair features:** IoU, centroid distance, area ratio, Hausdorff or Fréchet distance, shape descriptors, orientation difference, attribute similarity (survey number, owner name transliteration, ward).
3. **Scoring:** start with a hand-weighted score, then a gradient-boosted classifier trained on pairs you confirm.
4. **Global assignment** (Hungarian or greedy with 1-to-1 constraints), plus explicit **split and merge** detection (one-to-many, many-to-one).

### 6.5 Topology correction
Rules: no overlaps between parcels, no gaps below a sliver threshold, no self-intersections, buildings within parcels, utility lines connected (no dangles, undershoots). **Repairs must be bounded and auditable**: snap only within a tolerance, never invent geometry, log before/after, and refuse when ambiguous. **[A]**

### 6.6 Attribute mapping
Field-name matching across schemas (fuzzy string plus embedding similarity), value normalization, and transliteration for Indic scripts (owner names, village names). Link to **LGD codes** (Local Government Directory) for consistent state/district/ULB identifiers **[B]**. Keep the mapping **explainable**: show which signal produced each column match.

### 6.7 Change detection
- Vector change: matched, unmatched-new, unmatched-old, split, merge, moved (offset-aware).
- Raster change: requires two epochs of imagery. NAKSHA gives one epoch per ULB, so raster change for the demo needs a second image (older satellite or a second drone flight). **[A]** Make vector change the core, raster change a stretch goal.
- **Encroachment findings:** report as "findings for verification", never determinations. **[A]**

### 6.8 Conflict resolution and confidence
- Source hierarchy by survey method and accuracy (GNSS/CORS ground truth above drone-derived above municipal above legacy revenue), modulated by evidence and agreement between independent sources.
- **Never average two boundaries.** An averaged line belongs to no survey and cannot be defended in a dispute. Pick one source's observed geometry, or send to human review. (GeovaX makes the same point; it is good practice regardless.) **[A]**
- Confidence per feature: composed from positional agreement, source reliability, corroboration count, topology validity, attribute agreement and extractor confidence. Show grade A to E and **the reasons**.

## 7. What to build, and what to fake nothing about

**Must ship (the demo):**
1. Ingest: ORI as COG, vector layers (GeoJSON, GeoPackage, Shapefile), RoR CSV, GNSS CSV.
2. CRS engine with residual reporting and legacy-sheet rubber-sheeting from control points.
3. AI extraction on the demo AOI with polygon QC.
4. Matching with offset estimation, split/merge detection.
5. Topology validation with bounded repair.
6. Conflict engine implementing the NAKSHA three-tier protocol.
7. Confidence scoring with explanations.
8. Reviewer workbench: swipe compare, conflict queue, accept/reject, audit trail.
9. **Field queue:** risk-ranked list and map of parcels for GNSS ground truthing.
10. Export and API: GeoJSON/GeoPackage, OGC API Features.
11. Honest evaluation page: measured numbers and what they do not prove.

**Stretch:** nDSM heights and LOD1 buildings; utility topology checks; raster change; ULPIN linkage; webhooks.

**Do not build or claim:** legal title determination, official ULPIN issuance, fabricated departments or user counts, fake dashboards.

## 8. Differentiation plan

The repos above are backend-heavy. We win on:
1. **NAKSHA-native policy.** The three-tier reconciliation and 5% tolerance as the default engine, in the department's terms (Dispute/Anomaly, ground truthing, draft cards).
2. **Ground-truthing queue.** GT is the lagging stage nationally; ranking where surveyors should go first turns our confidence scores into an operational output.
3. **Land Stack fit.** Federated by design: each ULB or state runs its own instance and exposes OGC API Features plus a small platform API. Matches the DILRMP 3.0 language.
4. **A reviewer experience that is fast.** Keyboard-first queue, evidence card per conflict, one-click accept of the recommended source.
5. **Honest numbers.** Real open data on one small AOI, plus a separate, clearly labeled controlled experiment for accuracy. See `datasets.md`.

## 9. Risks

| Risk | Mitigation |
|---|---|
| No access to real NAKSHA ORI or state cadastral data | Use open drone imagery plus open footprints; say so on slide one. Offer an ingest path that accepts the real formats. |
| ML extraction fails in dense scenes | Show it on a medium-density AOI and show QC flagging bad polygons. Report failure cases. |
| Overclaiming legal effect | Include a "what this does not do" panel. Follow the paper's own caution that technology alone does not confer title. |
| Data licensing (ODbL share-alike, CC-BY attribution, non-commercial research sets) | Track licenses per dataset in the source registry. |
| Personal data (owner names) | Owner fields kept out of feature APIs; purpose-bound access; align with the DPDP Act **[B]**. |
| Time | Precompute heavy steps; keep AOI to roughly 1 to 3 km²; build the workbench early. |
| Hardware (16 GB RAM, integrated GPU) **[from your notes]** | Train or run heavy inference on Colab/Kaggle GPUs, ship precomputed outputs, keep runtime CPU-only. |

## 10. Suggested timeline

**Before the finale (now):** data acquisition and AOI selection; PostGIS schema; ingest and CRS; extraction run on Colab; matching prototype; workbench skeleton.
**During the finale:** conflict engine and confidence; field queue; evaluation page; polish; rehearse demo with a fixed script.
SIH 2026 grand finale dates: check the official SIH schedule. I did not verify them. **[A]**

## 11. Open questions to resolve with the organizers or mentors
- What formats do NAKSHA vendors actually deliver for feature extraction (GDB, SHP, GeoPackage)?
- Is there a standard attribute schema for the draft UrPro parcel layer?
- Is the 5% tolerance a policy number or an example from one state?
- Is there any sample dataset the ministry can share for the hackathon?

## Sources (opened this session)

- Frontiers in Sustainable Cities, NAKSHA scaling paper (Sep 2026): https://www.frontiersin.org/journals/sustainable-cities/articles/10.3389/frsc.2026.1874630/full
- DoLR NAKSHA booklet (PDF): https://cdnbbsr.s3waas.gov.in/s3d69116f8b0140cdeb1f99a4d5096ffe4/uploads/2025/03/20250311644815872.pdf
- AIR News on NAKSHA inauguration: https://www.newsonair.gov.in/madhya-pradesh-rural-development-minister-to-launch-naksha-for-urban-land-survey
- Rural Voice on DILRMP 3.0 and Land Stack: https://eng.ruralvoice.in/national/land-stack-every-land-parcel-to-receive-a-14-digit-bhu-aadhaar-ulpin-full-georeferencing-of-cadastral-maps.html
- DoLR ULPIN page: https://dolr.gov.in/en/ulpin/
- LBSNAA note on SoI CORS: https://rcentre.lbsnaa.gov.in/ebhuadhyan/CoursesContent/LandSurveyAndManagmentModule.html
- Cadastral boundary delineation study: https://doi.org/10.3390/rs11212505
- GeoAwesome on footprint QC: https://geoawesome.com/geoai-building-footprint-quality-control/
- GeovaX repo: https://github.com/sid-vj/GeovaX
