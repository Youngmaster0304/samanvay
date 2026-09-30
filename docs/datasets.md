# datasets.md

What to download, what each dataset is for, what to check before using it.

Tags: **[V]** verified this session from a source I opened. **[R]** reported by a third-party repo README (GeovaX), not verified by me. **[B]** background knowledge, confirm the link and licence yourself before relying on it.

## 0. Ground rules

1. **No real NAKSHA ORI or state cadastral vector is publicly available to us.** NAKSHA ORI is loaded onto the MPSEDC portal for state and field teams **[V]**. Say this on slide one. Build the ingest path for the real formats, and demo on open equivalents.
2. **Real data for the demo, labeled synthetic data only for controlled accuracy tests.** A matcher tuned on generated offsets learns the generator, so never present synthetic results as real-world performance. But a controlled experiment where you shift a real layer by a known vector is the only way to *measure* whether the offset estimator works, because real layers have no ground truth for the offset. Keep the two clearly separate in the evaluation page.
3. Record licence, source URL, vintage and SHA-256 for every file in a `source_registry` table (schema in `backend.md`).
4. ODbL is share-alike. If you merge ODbL data (OSM, Overture, Open Cities) into a published layer, that layer inherits ODbL. CC BY needs attribution. Track this per dataset.

## 1. Drone imagery and ORI equivalents (the "MAP-1" stand-in)

| Dataset | Use | Licence / access | Notes |
|---|---|---|---|
| **Open Cities AI Challenge** (GFDRR, Azavea, DrivenData) | Drone imagery plus hand-validated building footprints. Best open stand-in for "ORI plus reference footprints". Also a training and evaluation set for the extractor. | ODbL-1.0. Hosted on Source Cooperative. **[V]** | Over 400 km² of high-res drone imagery and about 790K footprints across 10+ African urban areas **[V]**. African context, not Indian. Say so. Imagery resolution varies by site. |
| **OpenDroneMap sample datasets** | Small raw-photo datasets with known good outputs. Lets you show a real photogrammetry-to-ORI chain and GCP handling. | Varies by dataset. **[R/B]** Check each dataset's page. | GeovaX reports using an ODM UAV corpus **[R]**. Pick one with GCPs so your CRS residual report is real. |
| **OpenAerialMap** | Community drone and aerial imagery, some in India. | Mostly CC BY 4.0, but licence is per image. **[B]** | Search for an Indian AOI with 5 to 15 cm imagery. If you find one, prefer it over the African set for the demo story. |
| Bangladesh UAV orthophotos (15 cm, Dhaka Division) | Referenced in a footprint-QC study. Regionally similar built form. | Availability unknown. **[V for study, unknown for data]** | Ask the authors or check the paper's data statement. |

**Recommendation [A]:** choose one AOI of 1 to 3 km², medium density, with imagery at 15 cm or better, and a reference footprint layer you trust. Convert to Cloud Optimized GeoTIFF and never touch the original again.

## 2. Building footprints (AI-derived layers to harmonize against)

| Dataset | Coverage | Licence | Notes |
|---|---|---|---|
| **Google Open Buildings V3 Polygons** | 1.8B buildings in Africa, Latin America, Caribbean, South Asia, Southeast Asia, derived from 50 cm satellite imagery **[V]** | CC BY 4.0 (some listings also mention ODbL) **[V]** | Includes a confidence score per polygon. Good as an "independent AI source" that disagrees with your drone extraction. Precision is lower than drone-derived. |
| **Open Buildings 2.5D Temporal** | Annual building presence, fractional counts and height, 2016 to 2023, at 4 m effective resolution, from Sentinel-2 **[V]** | CC BY 4.0 or ODbL, your choice **[V]** | Too coarse for parcel work. Useful only as a cheap "did something get built here?" signal. |
| **Overture Maps Buildings** | Global. Merges OSM, Esri Community Maps, Microsoft, Google Open Buildings and others **[V]** | ODbL **[V]** | Many features are ML-derived with lower precision **[V]**. Distributed as GeoParquet **[B]**. Useful as a ready-made "municipal-like" layer. |
| **Microsoft GlobalMLBuildingFootprints** | Global ML footprints **[B]** | ODbL **[B]** | Confirm India coverage and version. |
| **OpenStreetMap** (Geofabrik India extracts) | Community-mapped buildings, roads | ODbL **[B]** | Coverage in Indian towns varies. Good "municipal proxy" for roads and some buildings. |

Reported by GeovaX **[R]**: Greater Chennai Corporation building survey, AMRUT/Bhuvan footprints, TNGIS parcels (about 6M) and NCSCM parcels. If those are genuinely open, they would be the best Indian multi-source set for a real harmonization demo (several independent, disagreeing layers over the same ground). **Verify each portal's licence and terms before downloading.** Do not scrape portals whose terms forbid it.

## 3. Elevation (DSM/DTM)

| Dataset | Use | Notes |
|---|---|---|
| Your own DSM from the photogrammetry run (ODM) | Real DSM. Compute a DTM by ground filtering, then nDSM = DSM minus DTM for building heights and to validate footprints. | Best: same CRS and same date as your ORI. |
| **Copernicus GLO-30 DEM** | Free 30 m DSM. Context only. **[B]** | Too coarse for parcels. Useful for slope context and as a sanity layer. |
| Bhuvan / CartoDEM | Indian DEM. **[B]** | Registration required. Verify resolution and terms. |

## 4. Cadastral, revenue and municipal layers

Reality: Indian cadastral vector data is mostly served through state portals (Bhu-Naksha style) as view or print, not as bulk download **[B]**. Plan for three routes:

1. **Open Indian parcel layers if they exist for your AOI** (see the TNGIS/NCSCM report above **[R]**). Verify.
2. **Derive a "legacy cadastral" layer from a real source, then degrade it in a controlled, labeled way.** Example: take reference footprints as parcel proxies, apply a documented rubber-sheet distortion and rotation typical of scanned sheets, and store the true transformation as ground truth. This tests your georeferencing engine and is honest as long as it is labeled *simulated legacy sheet*.
3. **Scan and digitize one real old map yourself** (for example a public-domain survey sheet), place control points, and run your rubber-sheeting on it. Nothing shows the georeferencing feature better than a real scanned sheet snapping onto imagery.

**Revenue records (RoR/Khasra/Khata):** no open real data. Generate a **clearly labeled synthetic** RoR table with realistic structure (survey number, subdivision, area in local units, owner strings in Devanagari and Latin script, land-use class, tenure). Owner names must be fake and obviously fake. Never use real people. Label the table "SYNTHETIC" in the UI and in the source registry.

**Municipal layers:** OSM roads and Overture buildings as proxies. Ward boundaries: use the LGD-coded administrative boundaries if you can obtain them, otherwise label as approximate.

**Utilities:** no open Indian utility networks. Use OSM power lines and water features where mapped, or generate a **labeled synthetic** utility network (lines with deliberate dangles, undershoots and easement overlaps) purely to demonstrate topology rules. Do not present it as real.

## 5. GNSS and ground truthing

- **SoI CORS:** 1,047 permanent stations reported **[V]**. Access to real-time corrections needs application. **[B]** Do not depend on it for the demo.
- For the demo, the **GNSS/GT layer** should be a set of control points with accuracy attributes. Best source: the GCP file that ships with your drone dataset, if it has one. Otherwise derive check points from clearly identifiable features and label them as such.
- Format: CSV with `point_id, lat, lon, height, hdop or std_dev, fix_type, timestamp, method` plus RINEX and NMEA parsing as stretch.
- Carry each point's uncertainty through the pipeline. A GT point with 3 cm sigma should outrank a 1 m municipal line, and the confidence math should show why.

## 6. Training and evaluation datasets (ML side)

Use these to fine-tune or validate. All **[B]** unless marked. Confirm licence and current download location.

| Dataset | Task | Caution |
|---|---|---|
| Open Cities AI (above) **[V]** | Building segmentation from drone imagery | Africa. Fine for domain-adjacent training. |
| SpaceNet building sets | Building footprints, satellite | Check licence per SpaceNet round. |
| Inria Aerial Image Labeling | Building segmentation from aerial imagery | Research-use terms. Check. |
| WHU building dataset | Building segmentation and change | Check terms. |
| Massachusetts Buildings | Building segmentation | Older, US-specific. |
| CrowdAI Mapping Challenge | Small-tile building segmentation | Useful for quick baselines. |
| LEVIR-CD | Building change detection | Only needed if you attempt raster change. |
| ISPRS Potsdam / Vaihingen | Segmentation with DSM | Useful to test DSM-fusion. |
| its4land Rwanda UAV imagery (cadastral boundary work) | Visible cadastral boundary detection **[V for existence in papers]** | Data availability unclear. Ask authors. |

Pretrained model routes **[B]**: `segment-geospatial` (SAM wrapper for geospatial rasters), TorchGeo for datasets and baselines, and remote-sensing foundation models. Verify versions and weights licence when you pick one.

## 7. Reference data and standards

| Item | Use | Status |
|---|---|---|
| **ULPIN spec** (DoLR page) | 14-digit parcel ID, ECCMA/OGC aligned, vertex-derived **[V]** | Read it. Store a `ulpin` field and validate format only. |
| **LGD codes** (Local Government Directory) | Standard state/district/sub-district/village/ULB codes | **[B]** Download from the LGD portal. Use as the join key for attribute standardization. |
| OGC API - Features, GeoPackage, COG, STAC, GeoParquet, CityJSON | Export and exchange formats | **[B]** All open standards. |
| ISO 19152 (LADM), ISO 19157 (data quality) | Vocabulary for land administration and quality reporting | **[B]** Cite for credibility; do not claim compliance. |
| India geospatial data policy and DPDP Act | Governance and personal-data handling | **[B]** Read the current text before you make compliance statements. |

## 8. Suggested demo dataset bundle

Pick **one** of these and stick to it.

**Bundle A: Indian multi-source (best story, uncertain availability).**
Real Indian parcel and building layers for one AOI **[R, verify]**, plus drone or high-res imagery for the same AOI, plus synthetic RoR. Highest credibility if licences allow.

**Bundle B: Open, fully reproducible (safest).**
Open Cities drone tile(s) plus reference footprints, Google Open Buildings and Overture footprints for the same tile as independent AI/municipal sources, a simulated legacy sheet (labeled), synthetic RoR (labeled), and GCP-derived GNSS points. State the African imagery origin openly and show the pipeline is format-agnostic.

## 9. Evaluation datasets you must construct

| Experiment | How | What it proves | What it does not prove |
|---|---|---|---|
| Offset recovery | Shift a real layer by known vectors (0.5 to 5 m, plus rotation and mild scale). Run the estimator. Report error distribution. | The estimator recovers systematic shifts. | Real-world layers may have non-uniform distortion. |
| Match quality | Hand-label 200 to 300 pairs in the AOI as match / no-match / split / merge. Report precision, recall, F1. | Matcher accuracy on this AOI. | Generalization to other cities. |
| Topology repair | Count violations before and after repair. Manually audit 50 repairs. | Repairs are correct and bounded. | Legal correctness. |
| Extraction QC | Compare extractor output to reference footprints. Report F1/IoU before and after regularization. Show QC flags versus real errors. | Extractor plus QC quality on this AOI. | Dense-core performance. |
| Time saved | Time a person doing the same reconciliation manually in QGIS on a small subset. Compare. | A real, modest, reproducible speed-up figure. | Nationwide savings. |

Publish all numbers with the AOI size, hardware, and date. Any number without its limits attached will be picked apart by a judge with GIS experience.

## 10. Licence tracker (copy into the repo)

| Dataset | Licence | Attribution text | Share-alike? | Commercial OK? |
|---|---|---|---|---|
| Open Cities AI | ODbL-1.0 **[V]** | GFDRR Labs (2020), Open Cities AI Challenge Dataset | Yes | Yes with ODbL terms |
| Google Open Buildings | CC BY 4.0 **[V]** | Google Research, Open Buildings | No | Yes |
| Overture Buildings | ODbL **[V]** | Overture Maps Foundation | Yes | Yes with ODbL terms |
| OSM | ODbL **[B]** | OpenStreetMap contributors | Yes | Yes with ODbL terms |
| Others | Fill in as you download | | | |
